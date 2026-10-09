package com.dataghost.agent.models

import com.google.gson.annotations.SerializedName

/**
 * DataGhost Android Enterprise Agent – Data Contracts.
 *
 * These models map 1-to-1 with the DataGhost FastAPI backend schemas.
 * See backend/schemas/schemas.py for the authoritative definitions.
 */

// ── QR Code Payload ───────────────────────────────────────────────────────────

/**
 * Parsed from the enrollment QR code JSON string.
 *
 * Compatible with both the standard DataGhost QR format and the
 * Android Enterprise DPC provisioning format (which contains additional
 * `android.app.extra.*` keys that are ignored by Gson unless mapped).
 */
data class QrEnrollmentPayload(
    @SerializedName("version")    val version: String? = "1.0",
    @SerializedName("server_url") val serverUrl: String? = null,
    @SerializedName("token")      val token: String? = null,
    @SerializedName("code")       val code: String? = null,
    @SerializedName("platform")   val platform: String? = null,
    @SerializedName("expires_at") val expiresAt: String? = null,
)

// ── Enrollment Registration ───────────────────────────────────────────────────

/**
 * Sent to POST /api/devices/enrollment/register
 */
data class EnrollmentRegisterRequest(
    @SerializedName("token")           val token: String?,
    @SerializedName("enrollment_code") val enrollmentCode: String?,
    @SerializedName("device_name")     val deviceName: String,
    @SerializedName("platform")        val platform: String = "Android",
    @SerializedName("os_name")         val osName: String = "Android",
    @SerializedName("os_version")      val osVersion: String,
    @SerializedName("architecture")    val architecture: String,
    @SerializedName("hostname")        val hostname: String,
    @SerializedName("ip_address")      val ipAddress: String,
    @SerializedName("agent_version")   val agentVersion: String = "1.0.0",
    @SerializedName("device_metadata") val deviceMetadata: Map<String, Any>? = null,
)

/**
 * Response from POST /api/devices/enrollment/register
 */
data class EnrollmentRegisterResponse(
    @SerializedName("device_id")                  val deviceId: String,
    @SerializedName("device_name")                val deviceName: String,
    @SerializedName("platform")                   val platform: String,
    @SerializedName("status")                     val status: String,
    @SerializedName("auth_token")                 val authToken: String?,
    @SerializedName("heartbeat_interval_seconds") val heartbeatIntervalSeconds: Int,
    @SerializedName("server_time")                val serverTime: String,
    @SerializedName("message")                    val message: String,
)

// ── Heartbeat ─────────────────────────────────────────────────────────────────

/**
 * Sent to POST /api/devices/{device_id}/heartbeat
 */
data class HeartbeatRequest(
    @SerializedName("device_id")       val deviceId: String,
    @SerializedName("agent_version")   val agentVersion: String = "1.0.0",
    @SerializedName("status")          val status: String = "ACTIVE",
    @SerializedName("ip_address")      val ipAddress: String?,
    @SerializedName("files_scanned")   val filesScanned: Int,
    @SerializedName("incidents_count") val incidentsCount: Int,
    @SerializedName("cpu_usage")       val cpuUsage: Float? = null,
    @SerializedName("memory_usage")    val memoryUsage: Float? = null,
)

/**
 * Response from POST /api/devices/{device_id}/heartbeat
 */
data class HeartbeatResponse(
    @SerializedName("status")          val status: String,
    @SerializedName("device_id")       val deviceId: String,
    @SerializedName("last_seen")       val lastSeen: String,
    @SerializedName("policy_version")  val policyVersion: String,
    @SerializedName("ack_timestamp")   val ackTimestamp: String,
)

// ── DLP Scan ──────────────────────────────────────────────────────────────────

/**
 * Sent to POST /api/scan/text for Android content scanning.
 */
data class ScanTextRequest(
    @SerializedName("text")        val text: String,
    @SerializedName("filename")    val filename: String,
    @SerializedName("destination") val destination: String = "INTERNAL",
    @SerializedName("action")      val action: String = "READ",
    @SerializedName("device_id")   val deviceId: String,
    @SerializedName("user")        val user: String = "android_agent",
)

/**
 * Response from POST /api/scan/text
 */
data class ScanResponse(
    @SerializedName("filename")           val filename: String,
    @SerializedName("classification")     val classification: String,
    @SerializedName("risk_score")         val riskScore: Int,
    @SerializedName("severity")           val severity: String,
    @SerializedName("action_taken")       val actionTaken: String,
    @SerializedName("findings")           val findings: List<ScanFinding>,
    @SerializedName("incident_id")        val incidentId: String?,
)

data class ScanFinding(
    @SerializedName("rule_name")     val ruleName: String?,
    @SerializedName("category")      val category: String,
    @SerializedName("severity")      val severity: String,
    @SerializedName("matches_count") val matchesCount: Int?,
    @SerializedName("sample_match")  val sampleMatch: String?,
)
