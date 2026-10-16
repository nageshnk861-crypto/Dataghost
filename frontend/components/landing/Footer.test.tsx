import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Footer from './Footer';

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, className }: any) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

describe('Footer', () => {
  /**
   * Test: Footer renders without errors
   */
  it('should render footer without errors', () => {
    render(<Footer />);
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
  });

  /**
   * Test: Copyright text is displayed correctly
   */
  it('should display copyright text: "© 2024 DataGhost. All rights reserved."', () => {
    render(<Footer />);
    expect(screen.getByText('© 2024 DataGhost. All rights reserved.')).toBeInTheDocument();
  });

  /**
   * Test: Footer has correct background color (slate-900)
   */
  it('should have slate-900 background color', () => {
    const { container } = render(<Footer />);
    const footer = container.querySelector('footer');
    expect(footer).toHaveClass('bg-slate-900');
  });

  /**
   * Test: Footer has top border (border-slate-700)
   */
  it('should have top border with border-slate-700', () => {
    const { container } = render(<Footer />);
    const footer = container.querySelector('footer');
    expect(footer).toHaveClass('border-t', 'border-slate-700');
  });

  /**
   * Test: Footer displays all main sections
   */
  it('should display Product, Company, and Legal sections', () => {
    render(<Footer />);
    expect(screen.getByText('Product')).toBeInTheDocument();
    expect(screen.getByText('Company')).toBeInTheDocument();
    expect(screen.getByText('Legal')).toBeInTheDocument();
  });

  /**
   * Test: Product section has 4 links
   */
  it('should have Product section with 4 links', () => {
    render(<Footer />);
    expect(screen.getByText('Features')).toBeInTheDocument();
    expect(screen.getByText('Pricing')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(screen.getByText('Documentation')).toBeInTheDocument();
  });

  /**
   * Test: Company section has 4 links
   */
  it('should have Company section with 4 links', () => {
    render(<Footer />);
    expect(screen.getByText('About')).toBeInTheDocument();
    expect(screen.getByText('Blog')).toBeInTheDocument();
    expect(screen.getByText('Contact')).toBeInTheDocument();
    expect(screen.getByText('Careers')).toBeInTheDocument();
  });

  /**
   * Test: Legal section has 4 links
   */
  it('should have Legal section with 4 links', () => {
    render(<Footer />);
    expect(screen.getByText('Privacy Policy')).toBeInTheDocument();
    expect(screen.getByText('Terms of Service')).toBeInTheDocument();
    const legalCookies = screen.getAllByText('Cookies')[0];
    expect(legalCookies).toBeInTheDocument();
    expect(screen.getByText('License')).toBeInTheDocument();
  });

  /**
   * Test: All links have proper href attributes
   */
  it('should have all links with correct href attributes', () => {
    render(<Footer />);
    expect(screen.getByText('Features').closest('a')).toHaveAttribute('href', '#features');
    expect(screen.getByText('Pricing').closest('a')).toHaveAttribute('href', '/pricing');
    expect(screen.getByText('Security').closest('a')).toHaveAttribute('href', '/security');
    expect(screen.getByText('Documentation').closest('a')).toHaveAttribute('href', '/docs');
    expect(screen.getByText('About').closest('a')).toHaveAttribute('href', '/about');
    expect(screen.getByText('Blog').closest('a')).toHaveAttribute('href', '/blog');
    expect(screen.getByText('Contact').closest('a')).toHaveAttribute('href', '/contact');
    expect(screen.getByText('Careers').closest('a')).toHaveAttribute('href', '/careers');
  });

  /**
   * Test: Links have text-slate-400 color
   */
  it('should have footer links with text-slate-400 class', () => {
    const { container } = render(<Footer />);
    const footerGrid = container.querySelector('.grid');
    const links = footerGrid?.querySelectorAll('a') || [];
    expect(links.length).toBeGreaterThan(0);
    links.forEach((link) => {
      expect(link.className).toContain('text-slate-400');
    });
  });

  /**
   * Test: Links have hover effect (hover:text-slate-300)
   */
  it('should have footer links with hover:text-slate-300', () => {
    const { container } = render(<Footer />);
    const footerGrid = container.querySelector('.grid');
    const links = footerGrid?.querySelectorAll('a') || [];
    expect(links.length).toBeGreaterThan(0);
    links.forEach((link) => {
      expect(link.className).toContain('hover:text-slate-300');
    });
  });

  /**
   * Test: Links are keyboard accessible with focus ring
   */
  it('should have footer links with keyboard focus ring', () => {
    const { container } = render(<Footer />);
    const footerGrid = container.querySelector('.grid');
    const links = footerGrid?.querySelectorAll('a') || [];
    expect(links.length).toBeGreaterThan(0);
    links.forEach((link) => {
      expect(link.className).toContain('focus:ring-2');
      expect(link.className).toContain('focus:ring-indigo-500');
    });
  });

  /**
   * Test: Footer layout is responsive with grid classes
   */
  it('should have responsive grid layout classes', () => {
    const { container } = render(<Footer />);
    const footerGrid = container.querySelector('.grid');
    expect(footerGrid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3');
  });

  /**
   * Test: Footer has proper spacing with gap-8
   */
  it('should have proper spacing with gap-8', () => {
    const { container } = render(<Footer />);
    const footerGrid = container.querySelector('.grid');
    expect(footerGrid).toHaveClass('gap-8');
  });

  /**
   * Test: Section titles have correct styling
   */
  it('should have section titles with uppercase styling', () => {
    const { container } = render(<Footer />);
    const titles = container.querySelectorAll('h3');
    titles.forEach((title) => {
      expect(title).toHaveClass('uppercase', 'text-white', 'font-semibold');
    });
  });

  /**
   * Test: Footer has bottom section with copyright
   */
  it('should have bottom section with copyright text', () => {
    render(<Footer />);
    expect(screen.getByText('© 2024 DataGhost. All rights reserved.')).toBeInTheDocument();
  });

  /**
   * Test: Footer has divider between sections
   */
  it('should have divider border between main and bottom sections', () => {
    const { container } = render(<Footer />);
    const dividers = container.querySelectorAll('.border-t.border-slate-700');
    expect(dividers.length).toBeGreaterThanOrEqual(1);
  });

  /**
   * Test: Copyright section is responsive (flex-col on mobile, flex-row on desktop)
   */
  it('should have responsive copyright section', () => {
    const { container } = render(<Footer />);
    const copyrightSection = container.querySelector('.flex.flex-col');
    expect(copyrightSection).toBeInTheDocument();
  });

  /**
   * Test: Footer text has proper contrast (text-slate-400)
   */
  it('should have text-slate-400 for footer text ensuring proper contrast', () => {
    const { container } = render(<Footer />);
    const textElements = container.querySelectorAll('.text-slate-400');
    expect(textElements.length).toBeGreaterThan(0);
  });

  /**
   * Test: All sections rendered correctly
   */
  it('should render exactly 3 main footer sections', () => {
    const { container } = render(<Footer />);
    const sections = container.querySelectorAll('.grid > nav');
    expect(sections.length).toBe(3);
  });
});
