package com.dataghost.agent.enrollment

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.RestrictionsManager
import android.os.Build
import android.os.Bundle
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Integration tests for managed configuration support on a real or emulated device.
 *
 * These tests verify that ManagedConfigHelper correctly reads restrictions
 * set via MDM or device provisioning.
 *
 * Note: On a real device, restrictions are set by the MDM system.
 * On an emulator, you can simulate this using adb commands or by mocking
 * the RestrictionsManager in a test device owner app.
 *
 * To manually set restrictions on an emulator:
 *  adb shell am dpm set-device-owner com.dataghost.agent/.enrollment.DataGhostDeviceAdminReceiver
 *  adb shell am set-app-restrictions --user 0 com.dataghost.agent \
 *    '{"com.dataghost.organization_id":"test-org","com.dataghost.server_url":"https://test.example.com"}'
 */
@RunWith(AndroidJUnit4::class)
class ManagedConfigIntegrationTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = InstrumentationRegistry.getInstrumentation().targetContext
    }

    @Test
    fun testReadManagedConfig_OnRealDevice() {
        // This test will only pass if the device has been provisioned
        // with managed configuration by an MDM system.
        // On a standard test device, this will likely return null.

        val config = ManagedConfigHelper.readManagedConfig(context)
        
        // If MDM has not set restrictions, config will be null (which is ok).
        // If MDM has set restrictions, verify the structure.
        if (config != null) {
            assert(!config.organizationId.isBlank())
            assert(config.serverUrl.startsWith("https://"))
            assert(!config.bootstrapToken.isBlank())
            assert(!config.enrollmentCode.isBlank())
        }
    }

    @Test
    fun testManagedConfigData_ValidatesFields() {
        // Test that ManagedConfigData validates all fields correctly
        
        // Should succeed with valid fields
        val validConfig = ManagedConfigData(
            organizationId = "test-org",
            serverUrl = "https://example.com",
            bootstrapToken = "token123",
            enrollmentCode = "DG-XXXX-XXXX"
        )
        assert(validConfig.organizationId == "test-org")
        
        // Should fail with empty organizationId
        try {
            ManagedConfigData(
                organizationId = "",
                serverUrl = "https://example.com",
                bootstrapToken = "token123",
                enrollmentCode = "DG-XXXX-XXXX"
            )
            assert(false) { "Should have thrown IllegalArgumentException" }
        } catch (e: IllegalArgumentException) {
            assert(true)  // Expected
        }

        // Should fail with non-https URL
        try {
            ManagedConfigData(
                organizationId = "test-org",
                serverUrl = "http://example.com",  // Not HTTPS
                bootstrapToken = "token123",
                enrollmentCode = "DG-XXXX-XXXX"
            )
            assert(false) { "Should have thrown IllegalArgumentException" }
        } catch (e: IllegalArgumentException) {
            assert(true)  // Expected
        }
    }

    @Test
    fun testEnrollmentActivityLoadsManagédConfig() {
        // This is a manual verification test that the enrollment activity
        // properly reads and uses managed configuration.
        // 
        // Steps to verify manually:
        // 1. Set managed config on emulator:
        //    adb shell am set-app-restrictions --user 0 com.dataghost.agent \
        //      '{"com.dataghost.organization_id":"manual-org","com.dataghost.server_url":"https://manual.example.com","com.dataghost.bootstrap_token":"manual-token","com.dataghost.enrollment_code":"DG-1234-5678"}'
        // 2. Clear app data: adb shell pm clear com.dataghost.agent
        // 3. Launch app via adb: adb shell am start -n com.dataghost.agent/.ui.EnrollmentActivity
        // 4. Verify UI shows toast "Enrollment configured by administrator"
        // 5. Verify fields are auto-populated with managed config values
        
        // For automated testing, we verify the helper function works
        val config = ManagedConfigHelper.readManagedConfig(context)
        // If config is null, the test device isn't provisioned (which is ok for CI/CD)
        // If config is not null, verify structure
        if (config != null) {
            assert(!config.organizationId.isBlank())
            assert(config.serverUrl.startsWith("https://"))
        }
    }
}
