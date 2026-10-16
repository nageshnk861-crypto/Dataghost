import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import LandingPage from './LandingPage';

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href }: any) => (
    <a href={href}>{children}</a>
  ),
}));

describe('LandingPage', () => {
  /**
   * Test: Landing page renders without errors
   */
  it('should render landing page without errors', () => {
    render(<LandingPage />);
    expect(screen.getByText('DataGhost')).toBeInTheDocument();
  });

  /**
   * Test: Title and hero section are visible
   */
  it('should display hero section with main title', () => {
    render(<LandingPage />);
    expect(screen.getByText('AI-Powered Data Loss Prevention')).toBeInTheDocument();
    expect(
      screen.getByText(/Detect, monitor, and prevent data exfiltration/i)
    ).toBeInTheDocument();
  });

  /**
   * Test: Sign In links are present
   */
  it('should display sign in links', () => {
    render(<LandingPage />);
    const signInLinks = screen.getAllByText('Sign In');
    expect(signInLinks.length).toBeGreaterThanOrEqual(1);
  });

  /**
   * Test: Get Started button links to login
   */
  it('should have get started button linking to login', () => {
    render(<LandingPage />);
    const getStartedButton = screen.getByText('Get Started').closest('a');
    expect(getStartedButton).toHaveAttribute('href', '/login');
  });

  /**
   * Test: Features section displays all features
   */
  it('should display all feature cards', () => {
    render(<LandingPage />);
    expect(screen.getByText('Real-Time Detection')).toBeInTheDocument();
    expect(screen.getByText('Intelligent Blocking')).toBeInTheDocument();
    expect(screen.getByText('Analytics & Reporting')).toBeInTheDocument();
  });

  /**
   * Test: Feature descriptions are visible
   */
  it('should display feature descriptions', () => {
    render(<LandingPage />);
    expect(
      screen.getByText(/Monitor and detect sensitive data movements/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Automatically block and prevent unauthorized data exfiltration/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Comprehensive insights and reporting/i)
    ).toBeInTheDocument();
  });

  /**
   * Test: Footer is present
   */
  it('should display footer with copyright', () => {
    render(<LandingPage />);
    expect(screen.getByText(/© 2024 DataGhost/i)).toBeInTheDocument();
  });

  /**
   * Test: Learn More button exists
   */
  it('should have learn more button linking to features', () => {
    render(<LandingPage />);
    const learnMoreButton = screen.getByText('Learn More').closest('a');
    expect(learnMoreButton).toHaveAttribute('href', '#features');
  });

  /**
   * Test: Multiple Sign In buttons have correct links
   */
  it('should have all sign in buttons linking to login', () => {
    render(<LandingPage />);
    const links = screen.getAllByRole('link', { name: /sign in|get started/i });
    links.forEach((link) => {
      const href = link.getAttribute('href');
      expect(href === '/login' || href === '#features').toBe(true);
    });
  });

  /**
   * Test: Page has proper semantic structure
   */
  it('should have proper semantic structure', () => {
    render(<LandingPage />);
    // Check for navigation
    const headings = screen.getAllByRole('heading');
    expect(headings.length).toBeGreaterThan(0);
  });

  /**
   * Test: Landing page is responsive-friendly
   */
  it('should render with responsive classes', () => {
    const { container } = render(<LandingPage />);
    // Check for responsive Tailwind classes
    const responsiveElements = container.querySelectorAll('[class*="sm:"], [class*="md:"]');
    expect(responsiveElements.length).toBeGreaterThan(0);
  });
});
