package com.dataghost.agent.ui

import android.content.Intent
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.dataghost.agent.enrollment.EnrollmentManager

/**
 * DataGhost Android Enterprise Agent – Main Activity.
 *
 * Shown after successful enrollment. Displays:
 *  - Enrollment status (enrolled device ID and server URL)
 *  - Agent health (heartbeat status, files scanned, incidents)
 *  - Quick actions (view enrollment code, unenroll)
 *
 * For Fully Managed devices this is launched automatically after
 * DataGhostDeviceAdminReceiver.onProfileProvisioningComplete() completes.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var enrollmentManager: EnrollmentManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enrollmentManager = EnrollmentManager(this)

        // If not enrolled, redirect to enrollment
        if (!enrollmentManager.isEnrolled()) {
            startActivity(Intent(this, EnrollmentActivity::class.java))
            finish()
            return
        }

        setContentView(createMainLayout())

        // Handle success flag from DataGhostDeviceAdminReceiver
        if (intent.getBooleanExtra("enrollment_success", false)) {
            val deviceId = intent.getStringExtra("device_id") ?: ""
            Toast.makeText(
                this,
                "✓ Device enrolled successfully! ID: $deviceId",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private fun createMainLayout(): android.view.View {
        val ctx = this
        val prefs = getSharedPreferences("dataghost_agent_prefs", android.content.Context.MODE_PRIVATE)
        val deviceId   = prefs.getString("device_id", "Unknown") ?: "Unknown"
        val serverUrl  = prefs.getString("server_url", "Not set") ?: "Not set"
        val filesScanned   = prefs.getInt("files_scanned", 0)
        val incidentsCount = prefs.getInt("incidents_count", 0)

        return android.widget.ScrollView(ctx).apply {
            setBackgroundColor(0xFF0a0f1e.toInt())
            addView(
                android.widget.LinearLayout(ctx).apply {
                    orientation = android.widget.LinearLayout.VERTICAL
                    setPadding(64, 80, 64, 80)

                    // Header
                    addView(android.widget.TextView(ctx).apply {
                        text = "🛡️ DataGhost Agent"
                        textSize = 22f
                        setTextColor(0xFF00d4ff.toInt())
                        gravity = android.view.Gravity.CENTER
                        setPadding(0, 0, 0, 4)
                    })

                    addView(android.widget.TextView(ctx).apply {
                        text = "Enterprise DLP — Active"
                        textSize = 12f
                        setTextColor(0xFF34d058.toInt())
                        gravity = android.view.Gravity.CENTER
                        setPadding(0, 0, 0, 32)
                    })

                    // Status Card
                    addView(statusCard(ctx, "Device ID", deviceId, 0xFF00d4ff.toInt()))
                    addView(statusCard(ctx, "Server", serverUrl.take(45), 0xFF94a3b8.toInt()))
                    addView(statusCard(ctx, "Files Scanned", filesScanned.toString(), 0xFF60a5fa.toInt()))
                    addView(statusCard(ctx, "Security Incidents", incidentsCount.toString(),
                        if (incidentsCount > 0) 0xFFff9f0a.toInt() else 0xFF34d058.toInt()))
                    addView(statusCard(ctx, "Heartbeat", "Active (every 15 min)", 0xFF34d058.toInt()))

                    addView(android.widget.Space(ctx).apply { minimumHeight = 24 })

                    // Unenroll button
                    addView(android.widget.Button(ctx).apply {
                        text = "Unenroll Device"
                        setBackgroundColor(0xFF1a2744.toInt())
                        setTextColor(0xFFff3b3b.toInt())
                        setOnClickListener {
                            enrollmentManager.clearEnrollmentCredentials()
                            Toast.makeText(ctx, "Device unenrolled", Toast.LENGTH_SHORT).show()
                            startActivity(Intent(this@MainActivity, EnrollmentActivity::class.java))
                            finish()
                        }
                    })
                }
            )
        }
    }

    private fun statusCard(ctx: android.content.Context, label: String, value: String, valueColor: Int): android.view.View {
        return android.widget.LinearLayout(ctx).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            setPadding(24, 16, 24, 16)
            setBackgroundColor(0xFF0f1729.toInt())
            val lp = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.setMargins(0, 0, 0, 8)
            layoutParams = lp

            addView(android.widget.TextView(ctx).apply {
                text = label
                textSize = 12f
                setTextColor(0xFF475569.toInt())
                layoutParams = android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
            addView(android.widget.TextView(ctx).apply {
                text = value
                textSize = 12f
                setTextColor(valueColor)
                layoutParams = android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1.5f)
                maxLines = 2
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
        }
    }
}
