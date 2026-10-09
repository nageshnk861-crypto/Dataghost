package com.dataghost.agent.dlp

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.dataghost.agent.DataGhostApp
import com.dataghost.agent.models.ScanTextRequest
import com.dataghost.agent.models.ScanResponse
import com.google.gson.Gson
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * DataGhost Android Enterprise Agent – DLP Scanner Service.
 *
 * A foreground service that:
 *  1. Monitors content shared within the Android Work Profile
 *  2. Submits text content to /api/scan/text for classification
 *  3. Raises a local notification when sensitive content is detected (HIGH/CRITICAL)
 *
 * Uses Scoped Storage APIs — does NOT require root or system-level access.
 * Only scans files/content explicitly shared with the DataGhost agent via
 * the Android share sheet or Work Profile managed apps.
 *
 * In a production deployment this would also hook into:
 *  - FileObserver on Work Profile downloads directory
 *  - ContentObserver on MediaStore
 *  - Share intent receiver for text/file shares
 */
class DlpScannerService : Service() {

    companion object {
        private const val TAG = "DG_DLP"
        private const val NOTIFICATION_ID = 1001

        fun start(context: Context) {
            val intent = Intent(context, DlpScannerService::class.java)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, DlpScannerService::class.java))
        }
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, buildForegroundNotification())
        Log.i(TAG, "DLP Scanner Service started")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Restart service if killed by system
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        scope.cancel()
        Log.i(TAG, "DLP Scanner Service stopped")
        super.onDestroy()
    }

    // ── DLP Scanning ──────────────────────────────────────────────────────────

    /**
     * Scan text content via the DataGhost backend.
     *
     * Called when the Work Profile app receives shared text via share sheet,
     * or when a FileObserver detects a new file in the monitored directory.
     *
     * @param text     Content to scan (text extracted from file or share intent)
     * @param filename Filename for context (e.g. "document.pdf")
     * @param destination Where the data is going: INTERNAL, CLOUD, USB, EXTERNAL
     */
    fun scanContent(text: String, filename: String, destination: String = "INTERNAL") {
        scope.launch {
            val prefs = getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            val deviceId  = prefs.getString("device_id", "android-agent") ?: "android-agent"
            val serverUrl = prefs.getString("server_url", null) ?: return@launch
            val authToken = prefs.getString("auth_token", null)

            try {
                val scanRequest = ScanTextRequest(
                    text        = text,
                    filename    = filename,
                    destination = destination,
                    action      = if (destination == "INTERNAL") "READ" else "UPLOAD",
                    deviceId    = deviceId,
                    user        = "android_work_profile",
                )

                val jsonBody = gson.toJson(scanRequest)
                val body = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())
                val targetUrl = "${serverUrl.trimEnd('/')}/api/scan/text"

                val reqBuilder = Request.Builder()
                    .url(targetUrl)
                    .post(body)
                    .addHeader("X-Tunnel-Skip-Anti-Phishing-Page", "true")
                    .addHeader("bypass-tunnel-reminder", "true")

                if (!authToken.isNullOrBlank()) {
                    reqBuilder.addHeader("Authorization", "Bearer $authToken")
                }

                val response = client.newCall(reqBuilder.build()).execute()
                if (response.isSuccessful) {
                    val result = gson.fromJson(response.body?.string(), ScanResponse::class.java)
                    handleScanResult(result, filename)
                }
            } catch (e: Exception) {
                Log.w(TAG, "DLP scan error: ${e.message}")
            }
        }
    }

    private fun handleScanResult(result: ScanResponse, filename: String) {
        Log.d(TAG, "Scan: $filename → ${result.classification} (risk: ${result.riskScore})")

        // Update local counters in SharedPreferences
        val prefs = getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
        val scanned = prefs.getInt("files_scanned", 0) + 1
        prefs.edit().putInt("files_scanned", scanned).apply()

        if (result.severity == "HIGH" || result.severity == "CRITICAL") {
            val incidents = prefs.getInt("incidents_count", 0) + 1
            prefs.edit().putInt("incidents_count", incidents).apply()

            // Raise an alert notification
            showSecurityAlert(
                filename    = filename,
                severity    = result.severity,
                riskScore   = result.riskScore,
                classification = result.classification,
            )
        }
    }

    // ── Notifications ─────────────────────────────────────────────────────────

    private fun buildForegroundNotification(): Notification {
        return NotificationCompat.Builder(this, DataGhostApp.CHANNEL_ID_AGENT)
            .setContentTitle("DataGhost DLP Active")
            .setContentText("Monitoring work profile for data leakage")
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setSilent(true)
            .build()
    }

    private fun showSecurityAlert(
        filename: String,
        severity: String,
        riskScore: Int,
        classification: String,
    ) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager

        val alertNotification = NotificationCompat.Builder(this, DataGhostApp.CHANNEL_ID_ALERTS)
            .setContentTitle("⚠ DataGhost Security Alert — $severity")
            .setContentText("$filename classified as $classification (Risk: $riskScore/100)")
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("Sensitive content detected in '$filename'.\nClassification: $classification | Risk Score: $riskScore/100\nSeverity: $severity\n\nReview this incident in the DataGhost dashboard.")
            )
            .build()

        nm.notify(System.currentTimeMillis().toInt(), alertNotification)
    }
}
