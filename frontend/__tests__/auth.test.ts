import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  saveJwt,
  getJwt,
  removeJwt,
  saveUser,
  getSavedUser,
  fetchUserProfileFromBackend,
} from "../lib/auth";

describe("Phase 0: Role Persistence and Storage Helpers", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("0.1: saves and retrieves user object with id, email, username, and role", () => {
    const user = {
      id: 42,
      email: "analyst@dataghost.test",
      username: "test_analyst",
      role: "analyst",
    };

    saveUser(user);
    const retrieved = getSavedUser();

    expect(retrieved).not.toBeNull();
    expect(retrieved?.id).toBe(42);
    expect(retrieved?.email).toBe("analyst@dataghost.test");
    expect(retrieved?.username).toBe("test_analyst");
    expect(retrieved?.role).toBe("analyst");
  });

  it("0.1: persists JWT and user across simulated page navigation", () => {
    saveJwt("valid-jwt-token-123");
    saveUser({
      id: 1,
      email: "admin@dataghost.test",
      username: "admin_user",
      role: "admin",
    });

    // Simulate navigation by checking storage remains intact
    expect(getJwt()).toBe("valid-jwt-token-123");
    expect(getSavedUser()?.role).toBe("admin");
  });

  it("0.2: fetchUserProfileFromBackend fetches profile and returns role from backend", async () => {
    const mockProfile = {
      id: 99,
      username: "verified_user",
      email: "verified@dataghost.test",
      role: "admin",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockProfile,
    } as Response);

    const result = await fetchUserProfileFromBackend("mock-jwt-token");

    expect(result).not.toBeNull();
    expect(result?.username).toBe("verified_user");
    expect(result?.role).toBe("admin");
    expect(result?.email).toBe("verified@dataghost.test");
    expect(result?.isUnauthorized).toBe(false);
  });

  it("0.3: fetchUserProfileFromBackend detects 401 unauthorized status", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Unauthorized" }),
    } as Response);

    const result = await fetchUserProfileFromBackend("expired-jwt-token");

    expect(result).not.toBeNull();
    expect(result?.isUnauthorized).toBe(true);
  });

  it("0.3 & 0.4: logout removes both JWT and stored user profile", () => {
    saveJwt("test-jwt");
    saveUser({
      id: 10,
      username: "analyst",
      role: "analyst",
    });

    expect(getJwt()).toBe("test-jwt");
    expect(getSavedUser()).not.toBeNull();

    removeJwt();

    expect(getJwt()).toBeNull();
    expect(getSavedUser()).toBeNull();
  });
});
