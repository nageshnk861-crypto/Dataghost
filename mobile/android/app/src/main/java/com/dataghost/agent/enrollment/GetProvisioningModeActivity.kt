package com.dataghost.agent.enrollment

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.PersistableBundle
import android.util.Log

/**
 * DataGhost Android Enterprise – Get Provisioning Mode Activity (Android 12+ / API 31+).
 *
 * During modern Android Enterprise provisioning, the system setup wizard launches
 * this activity to query which provisioning mode the DPC supports.
 *
 * Modes:
 *   - PROVISIONING_MODE_FULLY_MANAGED_DEVICE (1): Device Owner / Corporate-owned
 *   - PROVISIONING_MODE_MANAGED_PROFILE (2): Work Profile / BYOD
 */
class GetProvisioningModeActivity : Activity() {

    companion object {
        private const val TAG = "DG_GetProvMode"
        const val PROVISIONING_MODE_FULLY_MANAGED_DEVICE = 1
        const val PROVISIONING_MODE_MANAGED_PROFILE = 2
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.i(TAG, "onCreate: received GET_PROVISIONING_MODE intent from Setup Wizard")

        val allowedModes = intent.getIntegerArrayListExtra(
            DevicePolicyManager.EXTRA_PROVISIONING_ALLOWED_PROVISIONING_MODES
        ) ?: arrayListOf()

        Log.i(TAG, "Allowed provisioning modes: $allowedModes")

        // Read the admin extras bundle
        val adminExtras: PersistableBundle? = intent.getParcelableExtra(
            DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE
        )

        // Select mode: Prioritize Fully Managed if allowed, otherwise Managed Profile
        val selectedMode = when {
            allowedModes.contains(PROVISIONING_MODE_FULLY_MANAGED_DEVICE) -> {
                Log.i(TAG, "Selecting PROVISIONING_MODE_FULLY_MANAGED_DEVICE (1)")
                PROVISIONING_MODE_FULLY_MANAGED_DEVICE
            }
            allowedModes.contains(PROVISIONING_MODE_MANAGED_PROFILE) -> {
                Log.i(TAG, "Selecting PROVISIONING_MODE_MANAGED_PROFILE (2)")
                PROVISIONING_MODE_MANAGED_PROFILE
            }
            else -> {
                // Fallback to fully managed if available, or first allowed
                allowedModes.firstOrNull() ?: PROVISIONING_MODE_FULLY_MANAGED_DEVICE
            }
        }

        val resultIntent = Intent().apply {
            putExtra(DevicePolicyManager.EXTRA_PROVISIONING_MODE, selectedMode)
            if (adminExtras != null) {
                putExtra(DevicePolicyManager.EXTRA_PROVISIONING_ADMIN_EXTRAS_BUNDLE, adminExtras)
            }
        }

        setResult(Activity.RESULT_OK, resultIntent)
        finish()
    }
}
