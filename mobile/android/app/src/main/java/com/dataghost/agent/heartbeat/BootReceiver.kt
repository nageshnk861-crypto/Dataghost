package com.dataghost.agent.heartbeat

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.*
import java.util.concurrent.TimeUnit

/**
 * Restarts the WorkManager heartbeat schedule after device reboot or app update.
 *
 * WorkManager periodic work survives reboots if RECEIVE_BOOT_COMPLETED is declared,
 * but re-enqueuing on boot is a safety net to ensure the job is always running.
 */
class BootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return

        val prefs = context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
        if (!prefs.getBoolean("is_enrolled", false)) return

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val heartbeatRequest = PeriodicWorkRequestBuilder<HeartbeatWorker>(
            15L, TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .addTag(DataGhostApp.HEARTBEAT_WORK_TAG)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30L, TimeUnit.SECONDS)
            .build()

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            DataGhostApp.HEARTBEAT_WORK_TAG,
            ExistingPeriodicWorkPolicy.KEEP,
            heartbeatRequest
        )
    }
}

// Alias for DataGhostApp companion constants (avoids import cycle)
private object DataGhostApp {
    const val HEARTBEAT_WORK_TAG = "dg_heartbeat_work"
}
