package com.dataghost.agent.enrollment

import android.app.admin.DeviceAdminReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.PersistableBundle
import android.util.Log
import com.dataghost.agent.DataGhostApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * DataGhost Android Enterprise – Device Policy Controller (DPC) Receiver.
 *
 * ══ ANDROID ENTERPRISE PROVISIONING — WHAT ACTUALLY HAPPENS ══════════════════
 *
 * FULLY MANAGED (Device Owner, corporate device, factory reset required):
 *   1. User factory-resets the device.
 *   2. On setup wizard, taps screen 6× quickly to trigger QR enrollment.
 *   3. Android downloads the DPC APK from PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION
 *      (must also provide PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM — SHA-256 of APK).
 *   4. Android installs the DPC and makes it Device Owner.
 *   5. Android calls ACTION_PROFILE_PROVISIONING_COMPLETE broadcast → this receiver.
 *      The intent carries PROVISIONING_ADMIN_EXTRAS_BUNDLE with our token.
 *   6. For Device Owner, Android also sends ACTION_PROVISIONING_SUCCESSFUL as an
 *      Activity intent (not broadcast) — a launcher Activity must handle it to
 *      complete the setup wizard. We handle both paths.
 *   NOTE: The user MUST complete Android's consent/management screens during setup.
 *         This is not "silent" from the user's perspective — Android shows
 *         "This device is managed by [org]" screens that the user acknowledges.
 *
 * WORK PROFILE (Profile Owner, BYOD — requires DataGhost Agent app installed):
 *   1. User installs the DataGhost Agent app from Play Store (or sideloads APK).
 *   2. App requests Work Profile creation (DataGhostApp.startManagedProfileProvisioning).
 *   3. Android creates a Work Profile and makes DataGhost its Profile Owner.
 *   4. Android calls ACTION_PROFILE_PROVISIONING_COMPLETE → this receiver.
 *   5. User sees Work Profile badge on apps — personal data stays private.
 *   NOTE: This path REQUIRES the DataGhost Agent app to be installed first.
 *         It is NOT app-free.
 *
 * ══ WHAT IS NOT IMPLEMENTED (requires additional Google configuration) ════════
 *
 *   - Zero-touch enrollment: Requires a Google Reseller or Google Zero-touch portal
 *     account. Cannot be configured from this codebase alone.
 *   - Android Management API (AMAPI): Would replace this custom DPC with Google's
 *     hosted EMM solution. Not used here — this is a custom DPC implementation.
 *   - Google Play EMM API: Not used here.
 *   - APK download: For fully managed, the QR payload needs a publicly accessible
 *     APK URL. In development, serve the debug APK via the dev tunnel.
 *
 * ══════════════════════════════════════════════════════════════════════════════
 */
class DataGhostDeviceAdminReceiver : DeviceAdminReceiver() {

    companion object {
        private const val TAG = "DG_DPC"

        // Keys injected via android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE
        const val EXTRA_SERVER_URL       = "com.dataghost.SERVER_URL"
        const val EXTRA_ENROLLMENT_TOKEN = "com.dataghost.ENROLLMENT_TOKEN"
        const val EXTRA_ENROLLMENT_CODE  = "com.dataghost.ENROLLMENT_CODE"
        const val EXTRA_EXPIRES_AT       = "com.dataghost.EXPIRES_AT"

        fun getComponentName(context: Context): ComponentName =
            ComponentName(context, DataGhostDeviceAdminReceiver::class.java)
    }

    // ── Provisioning Complete ─────────────────────────────────────────────────
    /**
     * Called by Android after BOTH Work Profile AND Fully Managed provisioning completes.
     *
     * For Fully Managed (Device Owner):
     *   This is a broadcast sent to the device owner's package after the device
     *   owner is set. The intent may contain PROVISIONING_ADMIN_EXTRAS_BUNDLE.
     *
     * For Work Profile (Profile Owner):
     *   This is sent after the work profile is created. The DPC should then
     *   enable the profile via DevicePolicyManager.setProfileEnabled().
     *
     * The user has ALREADY seen and acknowledged Android's management consent
     * screens by the time this callback fires. This callback is the signal
     * to complete our backend registration.
     */
    override fun onProfileProvisioningComplete(context: Context, intent: Intent) {
        super.onProfileProvisioningComplete(context, intent)
        Log.i(TAG, "onProfileProvisioningComplete fired — Android provisioning complete, starting backend registration")

        // For Work Profile: enable the profile so managed apps become visible
        try {
            val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE)
                as android.app.admin.DevicePolicyManager
            val component = getComponentName(context)
            if (dpm.isProfileOwnerApp(context.packageName)) {
                dpm.setProfileEnabled(component)
                Log.i(TAG, "Work Profile enabled")
            }
        } catch (e: Exception) {
            Log.w(TAG, "setProfileEnabled failed (may be device owner, not profile owner): ${e.message}")
        }

        handleProvisioningComplete(context, intent)
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device admin enabled")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device admin disabled — clearing enrollment state")
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .edit()
            .putBoolean("is_enrolled", false)
            .apply()
    }

    override fun onPasswordChanged(context: Context, intent: Intent) {
        Log.d(TAG, "Device password changed")
    }

    // ── Core: Handle Provisioning Extras and Register with Backend ────────────
    private fun handleProvisioningComplete(context: Context, intent: Intent) {
        val extras: PersistableBundle? =
            intent.getParcelableExtra("android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE")

        if (extras == null) {
            Log.w(TAG, "No PROVISIONING_ADMIN_EXTRAS_BUNDLE in intent — falling back to manual enrollment UI")
            // Admin enabled without our QR provisioning — open enrollment UI for manual entry
            launchEnrollmentActivity(context)
            return
        }

        val serverUrl       = extras.getString(EXTRA_SERVER_URL)       ?: ""
        val enrollmentToken = extras.getString(EXTRA_ENROLLMENT_TOKEN) ?: ""
        val enrollmentCode  = extras.getString(EXTRA_ENROLLMENT_CODE)  ?: ""

        if (serverUrl.isEmpty() || (enrollmentToken.isEmpty() && enrollmentCode.isEmpty())) {
            Log.w(TAG, "Provisioning extras present but missing required fields — launching enrollment UI")
            launchEnrollmentActivity(context)
            return
        }

        Log.i(TAG, "Provisioning extras received. Server: $serverUrl, Code: $enrollmentCode")

        // Persist server URL immediately so HeartbeatWorker can use it on next boot
        context.getSharedPreferences("dataghost_agent_prefs", Context.MODE_PRIVATE)
            .edit()
            .putString("server_url", serverUrl)
            .apply()

        // Call the DataGhost backend to register this device.
        // The device is NOT marked enrolled until this call succeeds.
        // The device is NOT marked online until the first heartbeat is received.
        CoroutineScope(Dispatchers.IO).launch {
            val manager = EnrollmentManager(context)
            val result = manager.registerDevice(
                serverUrl = serverUrl,
                token = enrollmentToken,
                enrollmentCode = enrollmentCode
            )

            result.onSuccess { response ->
                Log.i(TAG, "Backend registration successful. Device ID: ${response.deviceId}")
                // Only NOW schedule the heartbeat — device is confirmed enrolled
                val app = context.applicationContext as? DataGhostApp
                if (app != null) {
                    app.startHeartbeatAfterEnrollment()
                } else {
                    Log.e(TAG, "Failed to initialize heartbeat: DataGhostApp not available")
                }
                launchMainActivityWithResult(context, success = true, deviceId = response.deviceId)
            }.onFailure { err ->
                Log.e(TAG, "Backend registration failed: ${err.message}. Opening manual enrollment UI.")
                launchEnrollmentActivity(context)
            }
        }
    }

    private fun launchEnrollmentActivity(context: Context) {
        val i = Intent(context, Class.forName("com.dataghost.agent.ui.EnrollmentActivity"))
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        context.startActivity(i)
    }

    private fun launchMainActivityWithResult(context: Context, success: Boolean, deviceId: String = "") {
        val i = Intent(context, Class.forName("com.dataghost.agent.ui.MainActivity"))
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        i.putExtra("enrollment_success", success)
        i.putExtra("device_id", deviceId)
        context.startActivity(i)
    }
}
