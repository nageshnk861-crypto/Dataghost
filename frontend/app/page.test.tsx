import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import RootPage from './page';
import { useAuthContext } from '@/lib/AuthContext';
import { useRouter } from 'next/navigation';

// Mock the AuthContext
vi.mock('@/lib/AuthContext', () => ({
  useAuthContext: vi.fn(),
}));

// Mock LandingPage component
vi.mock('@/components/LandingPage', () => ({
  default: () => <div data-testid="landing-page">Landing Page</div>,
}));

describe('RootPage', () => {
  let mockRouter: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockRouter = {
      push: vi.fn(),
      replace: vi.fn(),
      back: vi.fn(),
      forward: vi.fn(),
    };
    
    // Mock useRouter
    vi.mocked(useRouter).mockReturnValue(mockRouter);
  });

  /**
   * Acceptance Criteria 1: Root page checks useAuthContext().isAuthenticated on client
   */
  it('should check authentication status on render', () => {
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    render(<RootPage />);

    expect(useAuthContext).toHaveBeenCalled();
  });

  /**
   * Acceptance Criteria 2: Unauthenticated users see landing page component (no redirect, actual content)
   */
  it('should render landing page for unauthenticated users', () => {
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    render(<RootPage />);

    expect(screen.getByTestId('landing-page')).toBeInTheDocument();
  });

  /**
   * Acceptance Criteria 3: Authenticated users are redirected to /incidents using router.replace()
   */
  it('should redirect authenticated users to /incidents', async () => {
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: true,
      authMethod: 'jwt',
      user: { username: 'testuser', role: 'analyst' },
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    render(<RootPage />);

    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith('/incidents');
    });
  });

  /**
   * Acceptance Criteria 4: Shows spinner/loading state while checking authentication
   */
  it('should show loading spinner while authReady is false', () => {
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: false,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    render(<RootPage />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  /**
   * Acceptance Criteria 5: Handles loading state properly (waits for authReady before rendering)
   */
  it('should wait for authReady before deciding what to render', async () => {
    const { rerender } = render(
      <RootPage />
    );

    // Initially loading
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: false,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    rerender(<RootPage />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();

    // Now auth is ready and not authenticated
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    rerender(<RootPage />);
    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
    });
  });

  /**
   * Acceptance Criteria 6: No errors in console when navigating between authenticated/unauthenticated states
   */
  it('should not produce console errors during auth state changes', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { rerender } = render(<RootPage />);

    // Simulate auth state changes
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: false,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    rerender(<RootPage />);

    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: false,
      authMethod: null,
      user: null,
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    rerender(<RootPage />);

    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: true,
      authMethod: 'jwt',
      user: { username: 'user', role: 'analyst' },
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    rerender(<RootPage />);

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  /**
   * Edge case: Should show redirect spinner while authenticated users are being redirected
   */
  it('should show redirect spinner for authenticated users during redirect', async () => {
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: true,
      authMethod: 'firebase',
      user: { username: 'firebaseuser@example.com', role: 'analyst' },
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    render(<RootPage />);

    // Should show redirect spinner before actual redirect
    expect(screen.getByText('Redirecting...')).toBeInTheDocument();
  });

  /**
   * Edge case: Multiple auth method types should all redirect
   */
  it('should redirect regardless of auth method (JWT or Firebase)', async () => {
    // Firebase auth should also redirect
    vi.mocked(useAuthContext).mockReturnValue({
      authReady: true,
      isAuthenticated: true,
      authMethod: 'firebase',
      user: { username: 'fbuser@example.com', role: 'analyst' },
      getAuthToken: vi.fn(),
      setJwtAuth: vi.fn(),
      signalAuthFailure: vi.fn(),
      logout: vi.fn(),
    });

    render(<RootPage />);

    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith('/incidents');
    });
  });
});
