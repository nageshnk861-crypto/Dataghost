package com.dataghost.agent.enrollment

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.PersistableBundle
import android.util.Log
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import com.dataghost.agent.DataGhostApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * DataGhost Android Enterprise – Admin Policy Compliance Activity (Android 12+ / API 31+).
 *
 * Launched by the Android Setup Wizard after provisioning to allow the DPC
 * to verify device compliance and complete backend registration before
 * transitioning to the device home screen.
 */
class AdminPolicyComplianceActivity : Activity() {

    companion object {
        private const val TAG = "DG_AdminCompliance"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "onCreate: received ADMIN_POLICY_COMPLIANCE intent from Setup Wizard")

        // Render a clean setup progress view
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(0xFF0a0f1e.toInt())
            setPadding(64, 64, 64, 64)

            addView(ProgressBar(this@AdminPolicyComplianceActivity).apply {
                isIndeterminate = true
            })
            addView(TextView(this@AdminPolicyComplianceActivity).apply {
                text = "Applying DataGhost Security Policies..."
                setTextColor(0xFF00d4ff.toInt())
                textSize = 16f
                gravity = Gravity.CENTER
                setPadding(0, 32, 0, 0)
            })
        }
        setContentView(layout)

        // Read provisioning admin extras bundle
        val adminExtras: PersistableBundle? = intent.getParcelableExtra(
            DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE
        )

        val serverUrl = adminExtras?.getString(DataGhostDeviceAdminReceiver.EXTRA_SERVER_URL) ?: ""
        val token = adminExtras?.getString(DataGhostDeviceAdminReceiver.EXTRA_ENROLLMENT_TOKEN) ?: ""
        val code = adminExtras?.getString(DataGhostDeviceAdminReceiver.EXTRA_ENROLLMENT_CODE) ?: ""

        val prefs = getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
        val isAlreadyEnrolled = prefs.getBoolean("is_enrolled", false)

        if (isAlreadyEnrolled) {
            Log.i(TAG, "Device already enrolled. Completing compliance.")
            completeCompliance()
            return
        }

        if (serverUrl.isNotEmpty() && (token.isNotEmpty() || code.isNotEmpty())) {
            prefs.edit().putString("server_url", serverUrl).apply()

            CoroutineScope(Dispatchers.IO).launch {
                val manager = EnrollmentManager(this@AdminPolicyComplianceActivity)
                val result = manager.registerDevice(
                    serverUrl = serverUrl,
                    token = token,
                    enrollmentCode = code
                )

                withContext(Dispatchers.Main) {
                    result.onSuccess { response ->
                        Log.i(TAG, "Compliance: device registered successfully. ID: ${response.deviceId}")
                        // Explicitly null-check the DataGhostApp instance before calling heartbeat
                        val app = applicationContext as? DataGhostApp
                        if (app != null) {
                            app.startHeartbeatAfterEnrollment()
                        } else {
                            Log.w(TAG, "App instance not available after enrollment")
                        }
                    }.onFailure { err ->
                        Log.w(TAG, "Compliance: background registration failed: ${err.message}. Proceeding with setup.")
                    }
                    completeCompliance()
                }
            }
        } else {
            Log.w(TAG, "No admin extras found in compliance intent. Completing compliance.")
            completeCompliance()
        }
    }

    private fun completeCompliance() {
        setResult(Activity.RESULT_OK)
        finish()
    }
}
