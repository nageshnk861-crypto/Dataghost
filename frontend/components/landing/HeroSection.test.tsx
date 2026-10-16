import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import HeroSection from './HeroSection';

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe('HeroSection Component', () => {
  /**
   * Test: Component renders without errors
   */
  it('should render hero section without errors', () => {
    render(<HeroSection />);
    expect(screen.getByText('AI-Powered Data Loss Prevention')).toBeInTheDocument();
  });

  /**
   * Test: Main headline is displayed correctly
   * Requirement 2.1: Hero section displays main headline: "AI-Powered Data Loss Prevention"
   */
  it('should display main headline "AI-Powered Data Loss Prevention"', () => {
    render(<HeroSection />);
    const headline = screen.getByRole('heading', { level: 1 });
    expect(headline).toHaveTextContent('AI-Powered Data Loss Prevention');
  });

  /**
   * Test: Subheadline is displayed correctly
   * Requirement 2.2: Subheadline: "Detect, monitor, and prevent data exfiltration in real time"
   */
  it('should display subheadline with key value proposition', () => {
    render(<HeroSection />);
    expect(
      screen.getByText('Detect, monitor, and prevent data exfiltration in real time')
    ).toBeInTheDocument();
  });

  /**
   * Test: Primary CTA button "Get Started" is present
   * Requirement 2.3 & 2.5: Primary CTA button links to /login
   */
  it('should display "Get Started" button linking to /login', () => {
    render(<HeroSection />);
    const getStartedButton = screen.getByRole('link', { name: /get started/i });
    expect(getStartedButton).toBeInTheDocument();
    expect(getStartedButton).toHaveAttribute('href', '/login');
  });

  /**
   * Test: Secondary CTA button "Learn More" is present
   * Requirement 2.4 & 2.6: Secondary CTA button links to #features
   */
  it('should display "Learn More" button linking to #features', () => {
    render(<HeroSection />);
    const learnMoreButton = screen.getByRole('link', { name: /learn more/i });
    expect(learnMoreButton).toBeInTheDocument();
    expect(learnMoreButton).toHaveAttribute('href', '#features');
  });

  /**
   * Test: Both CTA buttons are rendered
   * Requirement 2.3 & 2.4: Two CTA buttons present
   */
  it('should display both CTA buttons', () => {
    render(<HeroSection />);
    const getStartedButton = screen.getByRole('link', { name: /get started/i });
    const learnMoreButton = screen.getByRole('link', { name: /learn more/i });
    expect(getStartedButton).toBeInTheDocument();
    expect(learnMoreButton).toBeInTheDocument();
  });

  /**
   * Test: Buttons have proper ARIA labels
   * Requirement 5.1, 5.2, 5.3, 5.4: Accessibility - proper ARIA labels
   */
  it('should have proper ARIA labels for accessibility', () => {
    render(<HeroSection />);
    const getStartedButton = screen.getByRole('link', { name: /get started.*sign in/i });
    const learnMoreButton = screen.getByRole('link', { name: /learn more.*features/i });
    
    expect(getStartedButton).toHaveAttribute('aria-label');
    expect(learnMoreButton).toHaveAttribute('aria-label');
  });

  /**
   * Test: Container has proper background styling
   * Requirement 2.4: Hero uses gradient background (slate-900 to slate-800)
   */
  it('should have gradient background classes applied', () => {
    const { container } = render(<HeroSection />);
    const heroDiv = container.firstChild;
    expect(heroDiv).toHaveClass('bg-gradient-to-b', 'from-slate-900', 'to-slate-800');
  });

  /**
   * Test: Headline has responsive typography classes
   * Requirement 2.5, 5.1: Responsive text scaling (text-3xl sm:text-4xl md:text-5xl lg:text-6xl)
   */
  it('should have responsive typography classes on headline', () => {
    const { container } = render(<HeroSection />);
    const headline = container.querySelector('h1');
    expect(headline).toHaveClass(
      'text-3xl',
      'sm:text-4xl',
      'md:text-5xl',
      'lg:text-6xl',
      'font-bold',
      'text-white'
    );
  });

  /**
   * Test: Buttons stack vertically on mobile, horizontally on desktop
   * Requirement 5.5: Responsive layout with flex-col on mobile, flex-row on desktop
   */
  it('should have responsive button layout classes', () => {
    const { container } = render(<HeroSection />);
    const buttonContainer = container.querySelector('div.flex');
    expect(buttonContainer).toHaveClass('flex-col', 'sm:flex-row');
  });

  /**
   * Test: Buttons have hover and focus states
   * Requirement 2.6, 5.4: Buttons have hover effects and transitions
   */
  it('should have hover and focus state classes on buttons', () => {
    const { container } = render(<HeroSection />);
    const links = container.querySelectorAll('a');
    
    links.forEach(link => {
      const className = link.getAttribute('class') || '';
      // Check that buttons have hover/focus classes
      expect(className).toMatch(/hover:|focus:/);
      expect(className).toMatch(/transition/);
    });
  });

  /**
   * Test: Proper spacing and padding
   * Requirement 2.5: Proper spacing and typography hierarchy
   */
  it('should have proper spacing classes', () => {
    const { container } = render(<HeroSection />);
    const heroDiv = container.firstChild;
    expect(heroDiv).toHaveClass('py-16', 'sm:py-20', 'md:py-24', 'lg:py-32', 'px-4');
  });

  /**
   * Test: Full width container
   * Requirement 5.5: Full-width on mobile, constrained max-width on desktop
   */
  it('should be full-width with max-width constraint', () => {
    const { container } = render(<HeroSection />);
    const heroDiv = container.firstChild;
    expect(heroDiv).toHaveClass('w-full');
    
    const contentDiv = container.querySelector('.max-w-4xl');
    expect(contentDiv).toBeInTheDocument();
  });
});
