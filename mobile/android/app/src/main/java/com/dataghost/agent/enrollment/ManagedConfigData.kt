package com.dataghost.agent.enrollment

/**
 * DataGhost Android Enterprise Agent – Managed Configuration Data.
 *
 * Represents the configuration data read from Android's RestrictionsManager.
 * This is set by MDM (Mobile Device Management) systems or enterprise OEM configurations.
 *
 * All fields must be non-empty and valid before this class is instantiated.
 */
data class ManagedConfigData(
    val organizationId: String,
    val serverUrl: String,
    val bootstrapToken: String,
    val enrollmentCode: String,
) {
    init {
        require(organizationId.isNotBlank()) { "organizationId must not be empty" }
        require(serverUrl.isNotBlank()) { "serverUrl must not be empty" }
        require(serverUrl.startsWith("https://")) { "serverUrl must start with https://" }
        require(bootstrapToken.isNotBlank()) { "bootstrapToken must not be empty" }
        require(enrollmentCode.isNotBlank()) { "enrollmentCode must not be empty" }
    }
}
