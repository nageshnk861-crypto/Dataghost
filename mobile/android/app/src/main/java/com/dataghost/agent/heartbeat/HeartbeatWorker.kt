package com.dataghost.agent.heartbeat

import android.content.Context
import android.os.Build
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.dataghost.agent.models.HeartbeatRequest
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.net.NetworkInterface
import java.util.concurrent.TimeUnit

/**
 * DataGhost Android Enterprise Agent – Heartbeat Worker.
 *
 * Periodic WorkManager task that:
 *  1. Reads the device_id, auth_token, and server_url from SharedPreferences
 *  2. Collects current device metrics (files scanned, incidents, IP address)
 *  3. POST /api/devices/{device_id}/heartbeat
 *
 * Runs every 15 minutes (WorkManager minimum). Uses exponential backoff on failure.
 * The backend marks a device OFFLINE if no heartbeat is received within
 * DEVICE_HEARTBEAT_TIMEOUT_SECONDS (default 120s).
 */
class HeartbeatWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val prefs = applicationContext.getSharedPreferences(
            "dataghost_agent_prefs", Context.MODE_PRIVATE
        )

        val deviceId  = prefs.getString("device_id", null)  ?: return@withContext Result.failure()
        val serverUrl = prefs.getString("server_url", null)  ?: return@withContext Result.failure()
        val authToken = prefs.getString("auth_token", null)
        val isEnrolled = prefs.getBoolean("is_enrolled", false)

        if (!isEnrolled) return@withContext Result.failure()

        val filesScanned   = prefs.getInt("files_scanned", 0)
        val incidentsCount = prefs.getInt("incidents_count", 0)
        val ipAddress      = getLocalIpAddress()

        val payload = HeartbeatRequest(
            deviceId       = deviceId,
            agentVersion   = "1.0.0",
            status         = "ACTIVE",
            ipAddress      = ipAddress,
            filesScanned   = filesScanned,
            incidentsCount = incidentsCount,
            cpuUsage       = getCpuUsage(),
            memoryUsage    = getMemoryUsage(),
        )

        val jsonBody = gson.toJson(payload)
        val body = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())

        val targetUrl = "${serverUrl.trimEnd('/')}/api/devices/$deviceId/heartbeat"
        val reqBuilder = Request.Builder()
            .url(targetUrl)
            .post(body)
            .addHeader("X-Tunnel-Skip-Anti-Phishing-Page", "true")
            .addHeader("bypass-tunnel-reminder", "true")

        if (!authToken.isNullOrBlank()) {
            reqBuilder.addHeader("Authorization", "Bearer $authToken")
        }

        return@withContext try {
            val response = client.newCall(reqBuilder.build()).execute()
            if (response.isSuccessful) {
                Result.success()
            } else {
                Result.retry()
            }
        } catch (e: Exception) {
            Result.retry()
        }
    }

    // ── System Metrics ────────────────────────────────────────────────────────

    private fun getLocalIpAddress(): String? {
        return try {
            NetworkInterface.getNetworkInterfaces()
                ?.asSequence()
                ?.flatMap { it.inetAddresses.asSequence() }
                ?.firstOrNull { !it.isLoopbackAddress && !it.hostAddress.isNullOrEmpty() && !it.hostAddress!!.contains(':') }
                ?.hostAddress
        } catch (e: Exception) {
            null
        }
    }

    private fun getCpuUsage(): Float? {
        return try {
            // ProcessCpuTracker is internal — use /proc/stat on supported devices
            val stat = java.io.File("/proc/stat").readLines().firstOrNull() ?: return null
            val parts = stat.split("\\s+".toRegex()).drop(1).take(7).map { it.toLongOrNull() ?: 0L }
            val idle = parts.getOrElse(3) { 0L }
            val total = parts.sum()
            if (total == 0L) null else ((total - idle).toFloat() / total * 100f)
        } catch (e: Exception) {
            null
        }
    }

    private fun getMemoryUsage(): Float? {
        return try {
            val am = applicationContext.getSystemService(Context.ACTIVITY_SERVICE)
                    as android.app.ActivityManager
            val mi = android.app.ActivityManager.MemoryInfo()
            am.getMemoryInfo(mi)
            val used = mi.totalMem - mi.availMem
            (used.toFloat() / mi.totalMem * 100f)
        } catch (e: Exception) {
            null
        }
    }
}
