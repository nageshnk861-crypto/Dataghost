package com.dataghost.agent.enrollment

import android.content.Context
import android.content.RestrictionsManager
import android.os.Bundle
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner

/**
 * Unit tests for ManagedConfigHelper.
 *
 * Uses Robolectric to mock Android framework classes for local JVM unit tests.
 */
@RunWith(RobolectricTestRunner::class)
class ManagedConfigHelperTest {

    @Mock
    private lateinit var context: Context

    @Mock
    private lateinit var restrictionsManager: RestrictionsManager

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenRestrictionsManagerNull() {
        // Arrange
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(null)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenRestrictionsEmpty() {
        // Arrange
        val emptyBundle = Bundle()
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(emptyBundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenOrganizationIdMissing() {
        // Arrange
        val bundle = Bundle().apply {
            // Missing organizationId
            putString("com.dataghost.server_url", "https://example.com")
            putString("com.dataghost.bootstrap_token", "token123")
            putString("com.dataghost.enrollment_code", "DG-XXXX-XXXX")
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenServerUrlMissing() {
        // Arrange
        val bundle = Bundle().apply {
            putString("com.dataghost.organization_id", "org123")
            // Missing serverUrl
            putString("com.dataghost.bootstrap_token", "token123")
            putString("com.dataghost.enrollment_code", "DG-XXXX-XXXX")
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenBootstrapTokenMissing() {
        // Arrange
        val bundle = Bundle().apply {
            putString("com.dataghost.organization_id", "org123")
            putString("com.dataghost.server_url", "https://example.com")
            // Missing bootstrapToken
            putString("com.dataghost.enrollment_code", "DG-XXXX-XXXX")
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenEnrollmentCodeMissing() {
        // Arrange
        val bundle = Bundle().apply {
            putString("com.dataghost.organization_id", "org123")
            putString("com.dataghost.server_url", "https://example.com")
            putString("com.dataghost.bootstrap_token", "token123")
            // Missing enrollmentCode
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsNullWhenServerUrlNotHttps() {
        // Arrange
        val bundle = Bundle().apply {
            putString("com.dataghost.organization_id", "org123")
            putString("com.dataghost.server_url", "http://example.com")  // HTTP, not HTTPS
            putString("com.dataghost.bootstrap_token", "token123")
            putString("com.dataghost.enrollment_code", "DG-XXXX-XXXX")
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result == null)
    }

    @Test
    fun testReadManagedConfig_ReturnsValidConfigWhenAllFieldsPresent() {
        // Arrange
        val bundle = Bundle().apply {
            putString("com.dataghost.organization_id", "org123")
            putString("com.dataghost.server_url", "https://example.com")
            putString("com.dataghost.bootstrap_token", "token123")
            putString("com.dataghost.enrollment_code", "DG-XXXX-XXXX")
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result != null)
        assert(result?.organizationId == "org123")
        assert(result?.serverUrl == "https://example.com")
        assert(result?.bootstrapToken == "token123")
        assert(result?.enrollmentCode == "DG-XXXX-XXXX")
    }

    @Test
    fun testReadManagedConfig_TrimsWhitespace() {
        // Arrange
        val bundle = Bundle().apply {
            putString("com.dataghost.organization_id", "  org123  ")
            putString("com.dataghost.server_url", "  https://example.com  ")
            putString("com.dataghost.bootstrap_token", "  token123  ")
            putString("com.dataghost.enrollment_code", "  DG-XXXX-XXXX  ")
        }
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(bundle)

        // Act
        val result = ManagedConfigHelper.readManagedConfig(context)

        // Assert
        assert(result != null)
        assert(result?.organizationId == "org123")
        assert(result?.serverUrl == "https://example.com")
        assert(result?.bootstrapToken == "token123")
        assert(result?.enrollmentCode == "DG-XXXX-XXXX")
    }

    @Test
    fun testReadManagedConfig_HandlesNullRestrictions() {
        // Arrange
        whenever(context.getSystemService(Context.RESTRICTIONS_SERVICE))
            .thenReturn(restrictionsManager)
        whenever(restrictionsManager.applicationRestrictions)
            .thenReturn(null)

        // Act & Assert (should not crash)
        try {
            val result = ManagedConfigHelper.readManagedConfig(context)
            assert(result == null)
        } catch (e: Exception) {
            // Null restrictions should be handled gracefully
            assert(false) { "Should not throw exception: ${e.message}" }
        }
    }
}
