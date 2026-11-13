package com.dataghost.agent.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for EnrollmentActivity validation helpers.
 * These are pure-JVM tests (no Android framework required).
 */
class EnrollmentValidationTest {

    // ── Enrollment Code Validation ────────────────────────────────────────────

    @Test fun `valid code DG-8F3A-7B2C passes`() {
        assertTrue(EnrollmentActivity.validateEnrollmentCode("DG-8F3A-7B2C"))
    }

    @Test fun `valid code with all digits passes`() {
        assertTrue(EnrollmentActivity.validateEnrollmentCode("DG-1234-5678"))
    }

    @Test fun `valid code with all letters passes`() {
        assertTrue(EnrollmentActivity.validateEnrollmentCode("DG-ABCD-EFGH"))
    }

    @Test fun `lowercase code fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("dg-8f3a-7b2c"))
    }

    @Test fun `mixed case code fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("DG-8f3A-7b2C"))
    }

    @Test fun `code too short fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("DG-8F3A"))
    }

    @Test fun `code too long fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("DG-8F3A-7B2C-EXTRA"))
    }

    @Test fun `wrong prefix fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("ABC-1234-5678"))
    }

    @Test fun `empty string fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode(""))
    }

    @Test fun `code with special characters fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("DG-8F3@-7B2C"))
    }

    @Test fun `code with space fails`() {
        assertFalse(EnrollmentActivity.validateEnrollmentCode("DG-8F3A 7B2C"))
    }

    // ── Server URL Validation ─────────────────────────────────────────────────

    @Test fun `https URL passes`() {
        assertTrue(EnrollmentActivity.validateServerUrl("https://dataghost.onrender.com"))
    }

    @Test fun `http URL passes`() {
        assertTrue(EnrollmentActivity.validateServerUrl("http://localhost:8000"))
    }

    @Test fun `https with port passes`() {
        assertTrue(EnrollmentActivity.validateServerUrl("https://xxxx-8000.devtunnels.ms"))
    }

    @Test fun `ftp URL fails`() {
        assertFalse(EnrollmentActivity.validateServerUrl("ftp://example.com"))
    }

    @Test fun `URL without scheme fails`() {
        assertFalse(EnrollmentActivity.validateServerUrl("dataghost.onrender.com"))
    }

    @Test fun `empty string fails for URL`() {
        assertFalse(EnrollmentActivity.validateServerUrl(""))
    }

    @Test fun `bare IP without scheme fails`() {
        assertFalse(EnrollmentActivity.validateServerUrl("192.168.1.1:8000"))
    }
}
