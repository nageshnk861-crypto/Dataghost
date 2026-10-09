package com.dataghost.agent.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.dataghost.agent.DataGhostApp
import com.dataghost.agent.enrollment.EnrollmentManager
import com.dataghost.agent.enrollment.ManagedConfigHelper
import com.dataghost.agent.models.QrEnrollmentPayload
import com.google.gson.Gson
import kotlinx.coroutines.launch

/**
 * DataGhost Android Enterprise Agent – Enrollment Activity.
 *
 * Provides two enrollment paths:
 *   1. Camera QR Code scan — uses ML Kit Barcode Scanning (or ZXing)
 *   2. Manual entry — user types the DG-XXXX-XXXX code + server URL
 *
 * For Android Enterprise Fully Managed devices, this activity is rarely
 * shown — enrollment happens automatically via DataGhostDeviceAdminReceiver.
 * It is shown for:
 *   - Work Profile (BYOD) enrollment
 *   - Re-enrollment after factory reset when the DPC flow fails
 *   - Manual enrollment via text code (fallback)
 */
class EnrollmentActivity : AppCompatActivity() {

    private lateinit var enrollmentManager: EnrollmentManager
    private val gson = Gson()

    // Direct references to UI elements (stored during layout creation)
    private var serverUrlInput: android.widget.EditText? = null
    private var codeInput: android.widget.EditText? = null
    private var statusText: android.widget.TextView? = null
    private var scanButton: android.widget.Button? = null
    private var enrollButton: android.widget.Button? = null

    // Camera permission launcher
    private val cameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startQrScanner()
        else showError("Camera permission is required to scan the QR code")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enrollmentManager = EnrollmentManager(this)

        // If already enrolled, skip to MainActivity
        if (enrollmentManager.isEnrolled()) {
            startActivity(Intent(this, MainActivity::class.java))
            finish()
            return
        }

        setContentView(createEnrollmentLayout())

        // Check for managed configuration first
        val managedConfig = ManagedConfigHelper.readManagedConfig(this)
        if (managedConfig != null) {
            // Auto-populate from managed config
            serverUrlInput?.setText(managedConfig.serverUrl)
            codeInput?.setText(managedConfig.enrollmentCode)
            Toast.makeText(
                this,
                "Enrollment configured by administrator",
                Toast.LENGTH_SHORT
            ).show()
            android.util.Log.i("EnrollmentActivity", "Managed config loaded for organization: ${managedConfig.organizationId}")
        }

        // Handle deep links: dataghost://enroll or https://.../enroll/{code}
        intent?.data?.let { uri -> processIntentUri(uri) }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        intent?.data?.let { uri -> processIntentUri(uri) }
    }

    private fun processIntentUri(uri: android.net.Uri) {
        val server: String
        val token: String
        val code: String

        if (uri.scheme == "dataghost" && uri.host == "enroll") {
            token = uri.getQueryParameter("token") ?: ""
            code = uri.getQueryParameter("code") ?: ""
            server = uri.getQueryParameter("server") ?: ""
        } else if (uri.scheme == "http" || uri.scheme == "https") {
            server = "${uri.scheme}://${uri.host}${if (uri.port != -1 && uri.port != 80 && uri.port != 443) ":${uri.port}" else ""}"
            token = uri.getQueryParameter("token") ?: ""
            code = uri.getQueryParameter("code")
                ?: uri.lastPathSegment?.takeIf { it != "enroll" && it.isNotBlank() }
                ?: ""
        } else {
            return
        }

        // Prefill the UI fields if present (using stored references with safe operators)
        if (server.isNotBlank()) {
            serverUrlInput?.setText(server)
        }
        if (code.isNotBlank()) {
            codeInput?.setText(code)
        }

        // If we have enough info, trigger enrollment automatically
        if (server.isNotBlank() && (token.isNotBlank() || code.isNotBlank())) {
            performEnrollment(serverUrl = server, token = token, code = code)
        }
    }

    // ── Layout (programmatic for minimal dependencies) ─────────────────────────
    private fun createEnrollmentLayout(): android.view.View {
        val ctx = this
        return android.widget.ScrollView(ctx).apply {
            addView(
                android.widget.LinearLayout(ctx).apply {
                    orientation = android.widget.LinearLayout.VERTICAL
                    setPadding(64, 80, 64, 80)

                    // Title
                    addView(android.widget.TextView(ctx).apply {
                        text = "DataGhost\nDevice Enrollment"
                        textSize = 24f
                        setTextColor(0xFFFFFFFF.toInt())
                        gravity = android.view.Gravity.CENTER
                        setPadding(0, 0, 0, 8)
                    })

                    addView(android.widget.TextView(ctx).apply {
                        text = "Enroll this device into your organization's\nDataGhost DLP management"
                        textSize = 13f
                        setTextColor(0xFF94a3b8.toInt())
                        gravity = android.view.Gravity.CENTER
                        setPadding(0, 0, 0, 40)
                    })

                    // QR Scan Button
                    addView(android.widget.Button(ctx).apply {
                        id = android.R.id.button1
                        text = "📷  Scan Enrollment QR Code"
                        setOnClickListener { requestCameraAndScan() }
                        scanButton = this
                    })

                    addView(android.widget.TextView(ctx).apply {
                        text = "— or enter enrollment code manually —"
                        textSize = 11f
                        setTextColor(0xFF475569.toInt())
                        gravity = android.view.Gravity.CENTER
                        setPadding(0, 24, 0, 16)
                    })

                    // Server URL input
                    addView(android.widget.EditText(ctx).apply {
                        id = android.R.id.edit
                        hint = "Server URL (e.g. https://xxxx-8000.devtunnels.ms)"
                        inputType = android.text.InputType.TYPE_CLASS_TEXT or
                                android.text.InputType.TYPE_TEXT_VARIATION_URI
                        setPadding(24, 16, 24, 16)
                        serverUrlInput = this
                    })

                    addView(android.widget.Space(ctx).apply {
                        minimumHeight = 12
                    })

                    // Code input
                    addView(android.widget.EditText(ctx).apply {
                        id = android.R.id.text1
                        hint = "Enrollment Code (DG-XXXX-XXXX)"
                        inputType = android.text.InputType.TYPE_CLASS_TEXT or
                                android.text.InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
                        setPadding(24, 16, 24, 16)
                        codeInput = this
                    })

                    addView(android.widget.Space(ctx).apply { minimumHeight = 20 })

                    // Enroll Button
                    addView(android.widget.Button(ctx).apply {
                        id = android.R.id.button2
                        text = "Enroll Device"
                        setOnClickListener {
                            val serverUrl = serverUrlInput?.text?.toString()?.trim() ?: ""
                            val code = codeInput?.text?.toString()?.trim()?.uppercase() ?: ""
                            if (serverUrl.isEmpty() || code.isEmpty()) {
                                showError("Please enter both the server URL and enrollment code")
                                return@setOnClickListener
                            }
                            performEnrollment(serverUrl = serverUrl, token = "", code = code)
                        }
                        enrollButton = this
                    })

                    // Status text
                    addView(android.widget.TextView(ctx).apply {
                        id = android.R.id.message
                        text = ""
                        textSize = 12f
                        setTextColor(0xFF94a3b8.toInt())
                        gravity = android.view.Gravity.CENTER
                        setPadding(0, 16, 0, 0)
                        statusText = this
                    })
                }
            )
        }
    }

    // ── QR Scanner ────────────────────────────────────────────────────────────

    private fun requestCameraAndScan() {
        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
                    PackageManager.PERMISSION_GRANTED -> startQrScanner()
            else -> cameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startQrScanner() {
        // In production: integrate ML Kit Barcode Scanning or ZXing here.
        // For this reference implementation, we show a toast directing users to the manual flow.
        Toast.makeText(
            this,
            "QR scanner requires ML Kit integration. Use manual code entry below.",
            Toast.LENGTH_LONG
        ).show()
    }

    fun onQrCodeScanned(rawValue: String) {
        val payload = enrollmentManager.parseQrCode(rawValue)
        if (payload == null) {
            showError("Invalid QR code. Please scan a DataGhost enrollment QR code.")
            return
        }
        performEnrollment(
            serverUrl = payload.serverUrl ?: "",
            token     = payload.token     ?: "",
            code      = payload.code      ?: "",
        )
    }

    // ── Enrollment ────────────────────────────────────────────────────────────

    private fun performEnrollment(serverUrl: String, token: String, code: String) {
        setStatus("Enrolling device…")
        setButtonsEnabled(false)

        lifecycleScope.launch {
            val result = enrollmentManager.registerDevice(
                serverUrl = serverUrl,
                token = token,
                enrollmentCode = code,
            )

            result.onSuccess { response ->
                setStatus("✓ Enrolled as ${response.deviceName}")
                // Explicitly null-check the DataGhostApp instance before calling heartbeat
                val app = applicationContext as? DataGhostApp
                if (app != null) {
                    app.startHeartbeatAfterEnrollment()
                } else {
                    android.util.Log.e("EnrollmentActivity", "Failed to start heartbeat: DataGhostApp not available")
                }
                android.os.Handler(mainLooper).postDelayed({
                    startActivity(Intent(this@EnrollmentActivity, MainActivity::class.java))
                    finish()
                }, 1500)
            }.onFailure { err ->
                setStatus("")
                showError("Enrollment failed: ${err.message}")
                setButtonsEnabled(true)
            }
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun setStatus(msg: String) {
        runOnUiThread {
            statusText?.text = msg
        }
    }

    private fun setButtonsEnabled(enabled: Boolean) {
        runOnUiThread {
            scanButton?.isEnabled = enabled
            enrollButton?.isEnabled = enabled
        }
    }

    private fun showError(msg: String) {
        runOnUiThread {
            Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
        }
    }
}
