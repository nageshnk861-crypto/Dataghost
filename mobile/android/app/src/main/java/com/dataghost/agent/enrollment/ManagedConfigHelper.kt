package com.dataghost.agent.enrollment

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.os.Build
import android.util.Log

/**
 * DataGhost Android Enterprise Agent – Managed Configuration Helper.
 *
 * Reads organizational provisioning data from Android's RestrictionsManager.
 * This allows MDM systems to configure the DataGhost agent automatically,
 * enabling zero-touch enrollment.
 *
 * Expected restriction keys (set by MDM):
 *  - com.dataghost.organization_id: Organization identifier
 *  - com.dataghost.server_url: DataGhost backend URL (must be https://)
 *  - com.dataghost.bootstrap_token: One-time bootstrap token
 *  - com.dataghost.enrollment_code: Enrollment code (DG-XXXX-XXXX)
 *
 * Returns null if any required field is missing or invalid.
 */
object ManagedConfigHelper {

    private const val TAG = "ManagedConfigHelper"

    // Restriction keys set by MDM
    private const val KEY_ORGANIZATION_ID = "com.dataghost.organization_id"
    private const val KEY_SERVER_URL = "com.dataghost.server_url"
    private const val KEY_BOOTSTRAP_TOKEN = "com.dataghost.bootstrap_token"
    private const val KEY_ENROLLMENT_CODE = "com.dataghost.enrollment_code"

    /**
     * Read managed configuration from RestrictionsManager.
     *
     * @param context Android context used to access RestrictionsManager
     * @return ManagedConfigData if valid config found, null otherwise
     */
    fun readManagedConfig(context: Context): ManagedConfigData? {
        return try {
            // Get RestrictionsManager to read MDM-set restrictions
            val manager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                context.getSystemService(Context.RESTRICTIONS_SERVICE) as? android.content.RestrictionsManager
            } else {
                // Fallback for older Android versions
                context.getSystemService("restrictions") as? android.content.RestrictionsManager
            }

            if (manager == null) {
                Log.d(TAG, "RestrictionsManager not available")
                return null
            }

            val restrictions = manager.applicationRestrictions
            if (restrictions?.isEmpty != false) {
                Log.d(TAG, "No managed application restrictions found")
                return null
            }

            // Extract fields from restrictions bundle
            val organizationId = restrictions.getString(KEY_ORGANIZATION_ID)?.trim()
            val serverUrl = restrictions.getString(KEY_SERVER_URL)?.trim()
            val bootstrapToken = restrictions.getString(KEY_BOOTSTRAP_TOKEN)?.trim()
            val enrollmentCode = restrictions.getString(KEY_ENROLLMENT_CODE)?.trim()

            // Validate all fields are present and non-empty
            if (organizationId.isNullOrEmpty()) {
                Log.w(TAG, "organizationId missing or empty")
                return null
            }
            if (serverUrl.isNullOrEmpty()) {
                Log.w(TAG, "serverUrl missing or empty")
                return null
            }
            if (bootstrapToken.isNullOrEmpty()) {
                Log.w(TAG, "bootstrapToken missing or empty")
                return null
            }
            if (enrollmentCode.isNullOrEmpty()) {
                Log.w(TAG, "enrollmentCode missing or empty")
                return null
            }

            // Validate serverUrl format
            if (!serverUrl.startsWith("https://")) {
                Log.w(TAG, "serverUrl does not start with https://")
                return null
            }

            // Create and validate ManagedConfigData (init block will throw if invalid)
            val config = ManagedConfigData(
                organizationId = organizationId,
                serverUrl = serverUrl,
                bootstrapToken = bootstrapToken,
                enrollmentCode = enrollmentCode,
            )

            Log.i(TAG, "Successfully read managed config for organization: $organizationId")
            config

        } catch (e: Exception) {
            Log.e(TAG, "Error reading managed config: ${e.message}", e)
            null
        }
    }
}
