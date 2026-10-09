package com.dataghost.agent

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import androidx.work.*
import com.dataghost.agent.heartbeat.HeartbeatWorker
import com.dataghost.agent.enrollment.ManagedConfigHelper
import java.util.concurrent.TimeUnit

/**
 * DataGhost Android Enterprise Agent – Application Entry Point.
 *
 * Initialises WorkManager for periodic heartbeat and creates
 * the notification channels required by foreground services.
 */
class DataGhostApp : Application() {

    companion object {
        const val CHANNEL_ID_AGENT      = "dg_agent_channel"
        const val CHANNEL_ID_ALERTS     = "dg_alerts_channel"
        const val HEARTBEAT_WORK_TAG    = "dg_heartbeat_work"
        const val HEARTBEAT_INTERVAL_MIN = 15L  // WorkManager minimum is 15 minutes
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        
        // On first app start, attempt to read managed config and pre-populate SharedPreferences
        initializeManagedConfig()
        
        scheduleHeartbeat()
    }

    /**
     * On first app start, check for managed configuration and pre-initialize enrollment parameters.
     * This allows the enrollment flow to be skipped if the device is properly provisioned.
     */
    private fun initializeManagedConfig() {
        val prefs = getSharedPreferences("dataghost_agent_prefs", MODE_PRIVATE)
        val isFirstRun = !prefs.contains("first_run_completed")
        
        if (!isFirstRun || prefs.getBoolean("is_enrolled", false)) {
            return  // Not first run or already enrolled
        }

        val managedConfig = ManagedConfigHelper.readManagedConfig(this)
        if (managedConfig != null) {
            try {
                // Pre-populate enrollment parameters from managed config
                prefs.edit()
                    .putString("managed_org_id", managedConfig.organizationId)
                    .putString("managed_server_url", managedConfig.serverUrl)
                    .putString("managed_bootstrap_token", managedConfig.bootstrapToken)
                    .putString("managed_enrollment_code", managedConfig.enrollmentCode)
                    .putBoolean("has_managed_config", true)
                    .putBoolean("first_run_completed", true)
                    .apply()
                
                android.util.Log.i("DataGhostApp", "Managed config pre-initialized for organization: ${managedConfig.organizationId}")
            } catch (e: Exception) {
                android.util.Log.e("DataGhostApp", "Error pre-initializing managed config: ${e.message}", e)
                prefs.edit().putBoolean("first_run_completed", true).apply()
            }
        } else {
            // No managed config found, mark first run as complete
            prefs.edit().putBoolean("first_run_completed", true).apply()
        }
    }

    // ── Notification Channels ─────────────────────────────────────────────────
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)

            // Agent status / foreground service channel
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID_AGENT,
                    "DataGhost Agent",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "DataGhost DLP agent background status"
                    setShowBadge(false)
                }
            )

            // DLP alert channel
            nm.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID_ALERTS,
                    "DataGhost Security Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "DataGhost DLP security incident notifications"
                }
            )
        }
    }

    // ── Heartbeat WorkManager Scheduling ─────────────────────────────────────
    private fun scheduleHeartbeat() {
        val prefs = getSharedPreferences("dataghost_agent_prefs", MODE_PRIVATE)
        if (!prefs.getBoolean("is_enrolled", false)) return  // Don't heartbeat if not enrolled

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val heartbeatRequest = PeriodicWorkRequestBuilder<HeartbeatWorker>(
            HEARTBEAT_INTERVAL_MIN, TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .addTag(HEARTBEAT_WORK_TAG)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            HEARTBEAT_WORK_TAG,
            ExistingPeriodicWorkPolicy.KEEP,
            heartbeatRequest
        )
    }

    /**
     * Called after enrollment completes to kick off the heartbeat schedule.
     */
    fun startHeartbeatAfterEnrollment() {
        scheduleHeartbeat()
    }
}
