package com.dataghost.agent.enrollment

import android.content.Context
import android.os.Build
import android.util.Log
import com.dataghost.agent.models.EnrollmentRegisterRequest
import com.dataghost.agent.models.EnrollmentRegisterResponse
import com.dataghost.agent.models.QrEnrollmentPayload
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
 * DataGhost Android Enterprise Agent – Enrollment Manager.
 *
 * Handles:
 *  - Parsing QR code JSON payloads (standard DataGhost + Android Enterprise DPC format)
 *  - Registering device with the DataGhost backend via /api/devices/enrollment/register
 *  - Persisting enrollment credentials (device_id, auth_token, server_url) in SharedPreferences
 *
 * Called by:
 *  - DataGhostDeviceAdminReceiver (automatic, during QR setup wizard provisioning)
 *  - EnrollmentActivity (manual, user-entered code or camera QR scan)
 */
class EnrollmentManager(private val context: Context) {

    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    // ── QR Code Parsing ───────────────────────────────────────────────────────

    /**
     * Parse the JSON string from a DataGhost enrollment QR code.
     *
     * Supports both the standard DataGhost payload and the Android Enterprise
     * DPC provisioning payload (which contains additional
     * `android.app.extra.PROVISIONING_*` keys).
     *
     * Returns null if the JSON is invalid or missing required fields.
     */
    fun parseQrCode(qrData: String): QrEnrollmentPayload? {
        val trimmed = qrData.trim()
        // If it's a URL (e.g. from Easy Enrollment: https://server.com/enroll/DG-XXXX-XXXX or dataghost://...)
        if (trimmed.startsWith("http://", ignoreCase = true) ||
            trimmed.startsWith("https://", ignoreCase = true) ||
            trimmed.startsWith("dataghost://", ignoreCase = true)) {
            try {
                val uri = android.net.Uri.parse(trimmed)
                val server = "${uri.scheme}://${uri.host}${if (uri.port != -1 && uri.port != 80 && uri.port != 443) ":${uri.port}" else ""}"
                val token = uri.getQueryParameter("token") ?: ""
                val code = uri.getQueryParameter("code")
                    ?: uri.lastPathSegment?.takeIf { it != "enroll" && it.isNotBlank() }
                    ?: ""
                if (server.isNotBlank() && (token.isNotBlank() || code.isNotBlank())) {
                    return QrEnrollmentPayload(
                        serverUrl = server,
                        token = token.ifBlank { null },
                        code = code.ifBlank { null },
                        platform = "Android"
                    )
                }
            } catch (e: Exception) {
                // fallback to JSON parse
            }
        }

        return try {
            val payload = gson.fromJson(trimmed, QrEnrollmentPayload::class.java)
            // Validate minimum required fields
            if (payload.serverUrl.isNullOrBlank() || (payload.token.isNullOrBlank() && payload.code.isNullOrBlank())) null
            else payload
        } catch (e: Exception) {
            null
        }
    }

    // ── Device Registration ───────────────────────────────────────────────────

    /**
     * Register this device with the DataGhost backend using a bootstrap token or enrollment code.
     *
     * On success: credentials are persisted in SharedPreferences and
     *             [DataGhostApp.startHeartbeatAfterEnrollment] should be called.
     *
     * @param serverUrl  The DataGhost backend URL (from QR code or user input)
     * @param token      The raw enrollment token (from QR code, optional)
     * @param bootstrapToken  The bootstrap token (from managed config, optional)
     * @param enrollmentCode  The human-readable DG-XXXX-XXXX code (fallback)
     */
    suspend fun registerDevice(
        serverUrl: String,
        token: String = "",
        enrollmentCode: String = "",
        bootstrapToken: String = ""
    ): Result<EnrollmentRegisterResponse> = withContext(Dispatchers.IO) {
        try {
            val deviceName = buildDeviceName()
            
            // Use bootstrap token if provided, otherwise fall back to enrollment code lookup
            val effectiveToken = if (bootstrapToken.isNotBlank()) {
                Log.i("EnrollmentManager", "Using bootstrap token from managed config")
                bootstrapToken
            } else {
                Log.i("EnrollmentManager", "Using token from enrollment code")
                token
            }

            val requestPayload = EnrollmentRegisterRequest(
                token = effectiveToken.ifBlank { null },
                enrollmentCode = enrollmentCode.ifBlank { null },
                deviceName = deviceName,
                platform = "Android",
                osName = "Android",
                osVersion = "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})",
                architecture = Build.SUPPORTED_ABIS.firstOrNull() ?: "arm64-v8a",
                hostname = Build.HOST ?: "android-device",
                ipAddress = getLocalIpAddress() ?: "0.0.0.0",
                agentVersion = "1.0.0",
                deviceMetadata = mapOf(
                    "brand"        to Build.BRAND,
                    "manufacturer" to Build.MANUFACTURER,
                    "model"        to Build.MODEL,
                    "sdk_int"      to Build.VERSION.SDK_INT,
                    "fingerprint"  to Build.FINGERPRINT.substringBefore("/"),
                )
            )

            val jsonBody = gson.toJson(requestPayload)
            val body = jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType())

            val targetUrl = "${serverUrl.trimEnd('/')}/api/devices/enrollment/register"
            val request = Request.Builder()
                .url(targetUrl)
                .post(body)
                // Bypass dev tunnel / proxy interstitial pages
                .addHeader("X-Tunnel-Skip-Anti-Phishing-Page", "true")
                .addHeader("bypass-tunnel-reminder", "true")
                .build()

            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val respBody = response.body?.string() ?: ""
                val registerResp = gson.fromJson(respBody, EnrollmentRegisterResponse::class.java)
                
                // Validate that the response parsed successfully with required fields
                // authToken is nullable, so we check before using it
                if (registerResp.authToken == null) {
                    Log.e("EnrollmentManager", "Response missing authToken")
                    return@withContext Result.failure(Exception("Response missing authToken"))
                }
                
                saveEnrollmentCredentials(registerResp.deviceId, registerResp.authToken, serverUrl)
                return@withContext Result.success(registerResp)
            } else {
                val errBody = response.body?.string() ?: "Registration failed (HTTP ${response.code})"
                return@withContext Result.failure(Exception(errBody))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun buildDeviceName(): String {
        val manufacturer = Build.MANUFACTURER.replaceFirstChar { it.uppercase() }
        val model = Build.MODEL
        // Avoid duplicating manufacturer name in model (e.g. "Samsung Samsung Galaxy S23")
        return if (model.startsWith(manufacturer, ignoreCase = true)) model else "$manufacturer $model"
    }

    private fun getLocalIpAddress(): String? {
        return try {
            NetworkInterface.getNetworkInterfaces()
                ?.asSequence()
                ?.flatMap { it.inetAddresses.asSequence() }
                ?.firstOrNull { !it.isLoopbackAddress && it.hostAddress?.contains(':') == false }
                ?.hostAddress
        } catch (e: Exception) {
            null
        }
    }

    private fun saveEnrollmentCredentials(deviceId: String, authToken: String?, serverUrl: String) {
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .edit()
            .putString("device_id", deviceId)
            .putString("auth_token", authToken)
            .putString("server_url", serverUrl)
            .putBoolean("is_enrolled", true)
            .apply()
    }

    /**
     * Clear all enrollment credentials (used during unenrollment / factory reset).
     */
    fun clearEnrollmentCredentials() {
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .edit().clear().apply()
    }

    fun isEnrolled(): Boolean =
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .getBoolean("is_enrolled", false)

    fun getSavedServerUrl(): String? =
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .getString("server_url", null)

    fun getSavedDeviceId(): String? =
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .getString("device_id", null)
}
