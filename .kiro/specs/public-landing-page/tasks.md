# Implementation Plan: Public Landing Page

## Overview

This implementation plan converts the landing page design into discrete, executable tasks for building a responsive, SEO-friendly entry point for DataGhost DLP. The tasks follow a logical sequence: first establishing authentication routing and component structure, then building individual sections with styling, followed by accessibility enhancements and testing. The approach prioritizes incremental progress and early validation.

---

## Tasks

- [x] 1. Set up landing page component structure and routing

  This is the foundation task that establishes the routing logic and component skeleton.

  - [x] 1.1 Create landing page directory and component files
    - Create `/app/landing/` directory
    - Create `LandingPage.tsx` as the main container component
    - Create component files: `HeroSection.tsx`, `FeaturesSection.tsx`, `FeatureCard.tsx`, `DashboardScreenshotSection.tsx`, `FooterSection.tsx`
    - Export all components with TypeScript interfaces
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Implement authentication routing in root page
    - Modify `/app/page.tsx` to check authentication status using NextAuth session or Firebase auth
    - If authenticated: redirect to `/dashboard`
    - If unauthenticated: render the `LandingPage` component
    - Ensure server-side rendering for performance
    - _Requirements: 1.2, 10.1, 10.2, 10.3_

  - [ ]* 1.3 Write property test for authentication routing
    - **Property 1: Unauthenticated Access Invariant**
    - **Property 2: Authenticated Redirect Invariant**
    - **Validates: Requirements 1.1, 1.2, 1.3, 10.2, 10.3**
    - Test that unauthenticated requests render landing page
    - Test that authenticated requests redirect to dashboard

- [ ] 2. Implement Hero Section with headline, subheading, and CTA buttons

  This task builds the above-the-fold hero component that captures attention and drives conversions.

  - [x] 2.1 Create and style Hero Section component
    - Implement `HeroSection.tsx` with headline, subheading, and CTA buttons
    - Add responsive typography (32px mobile, 48px desktop for headline)
    - Style primary "Sign In" button and secondary "Try Demo" button using existing Tailwind classes
    - Implement button click handlers: "Sign In" → `/login`, "Try Demo" → sign-up flow
    - Add proper ARIA labels to buttons for accessibility
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 2.2 Write property test for CTA button navigation
    - **Property 3: CTA Navigation Correctness**
    - **Validates: Requirements 2.5, 2.6, 5.3, 5.4**
    - Test that clicking "Sign In" navigates to `/login`
    - Test that clicking "Try Demo" navigates to sign-up flow
    - Test button rendering and presence in DOM

  - [~] 2.3 Make Hero Section responsive across all breakpoints
    - Adjust layout for mobile (320px–480px): center content, stack buttons vertically
    - Adjust layout for tablet (768px–1024px): optimize spacing and font sizes
    - Adjust layout for desktop (1024px+): full-width with balanced spacing
    - Test headline readability on all screen sizes
    - Use Tailwind responsive classes (sm:, md:, lg:, xl:)
    - _Requirements: 7.1, 7.2, 7.3, 8.1, 8.4, 9.1, 9.3_

- [ ] 3. Implement Features Section with 3 feature cards

  This task builds the core value proposition display showing DataGhost's key capabilities.

  - [x] 3.1 Create Feature Card component with icon, title, and description
    - Implement `FeatureCard.tsx` as a reusable card component
    - Accept props: icon (Lucide React), title, description
    - Add card styling: 24px padding, subtle border/shadow, 6px border-radius
    - Ensure icon displays properly (32px size for cards)
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Create Features Section and populate with 3 cards
    - Implement `FeaturesSection.tsx` with 3 feature cards:
      1. Secret Detection
      2. Risk Scoring & Classification
      3. Audit Logging & Compliance
    - Use Lucide React icons (Lock, AlertCircle, FileText or similar)
    - Add descriptive titles and descriptions for each card
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [~] 3.3 Implement responsive grid layout for feature cards
    - Mobile (< 768px): Single column, full-width cards stacked vertically
    - Tablet (768px–1024px): 2-column grid layout
    - Desktop (1024px+): 3-column grid layout with 24px gap
    - Use Tailwind grid classes (grid, grid-cols-1, md:grid-cols-2, lg:grid-cols-3)
    - _Requirements: 3.5, 3.6, 8.2_

  - [ ]* 3.4 Write property test for feature cards rendering and layout
    - **Property 4: Feature Cards Rendering**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5, 3.6**
    - Test that all 3 cards render with titles, descriptions, and icons
    - Test that grid layout changes based on viewport width
    - Test responsive behavior on mobile, tablet, and desktop

- [ ] 4. Implement Dashboard Screenshot Section with image and description

  This task adds visual proof of the dashboard to build visitor confidence.

  - [x] 4.1 Create Dashboard Screenshot Section component
    - Implement `DashboardScreenshotSection.tsx`
    - Add section heading: "See the DataGhost Dashboard in Action"
    - Add description text explaining what the screenshot shows
    - Use Next.js `Image` component for optimized loading (not `<img>`)
    - Set up image path: `/public/images/dashboard-screenshot.png` (placeholder during this task)
    - Add proper alt text: "DataGhost dashboard showing threat detection, risk metrics, and audit logs"
    - _Requirements: 4.1, 4.2, 4.3, 12.1_

  - [~] 4.2 Implement responsive image sizing and styling
    - Desktop: Image width ~85–90% of viewport with max-width 1200px
    - Tablet: Image full width with 16–24px side padding
    - Mobile: Image full width with 16px top/bottom padding
    - Add subtle border or shadow for visual hierarchy
    - Use Next.js Image `responsive` sizes for automatic srcSet generation
    - Implement lazy loading (image loads when in viewport)
    - _Requirements: 4.4, 4.5, 9.5_

  - [ ]* 4.3 Write property test for screenshot responsiveness
    - **Property 6: Dashboard Screenshot Responsiveness**
    - **Validates: Requirements 4.4, 4.5, 9.5**
    - Test that image scales correctly on mobile, tablet, and desktop
    - Test that image aspect ratio is maintained across breakpoints
    - Test that no horizontal scrolling occurs

- [ ] 5. Implement Footer Section and integrate all components

  This task completes the landing page layout and wires all sections together.

  - [x] 5.1 Create Footer Section component
    - Implement `FooterSection.tsx`
    - Add navigation links: "Contact Us", "Support", "Documentation" (optional)
    - Add legal links: "Privacy Policy", "Terms of Service", "Security" (optional)
    - Add copyright notice: "© 2025 DataGhost. All rights reserved."
    - Add social links (optional): GitHub, Twitter, LinkedIn (Lucide React icons)
    - Style footer with subtle background and muted text color
    - _Requirements: 6.1, 6.2, 6.3_

  - [~] 5.2 Make Footer responsive
    - Desktop (1024px+): Multi-column layout (3–4 columns)
    - Tablet (768px–1024px): 2-column layout
    - Mobile (< 768px): Single column, links stacked vertically
    - Use Tailwind responsive classes for layout changes
    - _Requirements: 6.1_

  - [x] 5.3 Integrate all sections into Landing Page component
    - Update `LandingPage.tsx` to render all sections in order:
      1. Header/Navigation (optional: create separate header or include in hero)
      2. HeroSection
      3. FeaturesSection
      4. DashboardScreenshotSection
      5. FooterSection
    - Ensure proper spacing between sections (48px–64px gaps using Tailwind)
    - Add max-width constraint to main container (1400px) for desktop
    - Test that all sections render without layout breaks
    - _Requirements: 2.1, 3.1, 4.1, 6.1, 11.1_

  - [ ]* 5.4 Write integration test for complete landing page layout
    - **Validates: Requirements 1.1, 2.1, 3.1, 4.1, 6.1, 11.1**
    - Test that all sections render on a single page
    - Test that content flows without layout issues
    - Test responsive behavior on mobile, tablet, desktop
    - Test that all CTAs are present and functional

- [ ] 6. Add styling consistency, accessibility, and performance optimization

  This final task ensures the landing page meets visual, accessibility, and performance standards.

  - [~] 6.1 Ensure visual consistency with DataGhost design system
    - Verify all components use existing Tailwind CSS configuration
    - Check color palette matches existing dashboard (primary, secondary, backgrounds, text colors)
    - Verify typography uses existing font scale (Inter font family already loaded)
    - Ensure all icons use Lucide React (consistent with app)
    - Add consistent button hover/focus states using Tailwind `hover:` and `focus:` variants
    - Test dark mode compatibility (if applicable)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 6.2 Implement accessibility features (keyboard navigation, ARIA, semantic HTML)
    - Add semantic HTML structure (proper heading hierarchy: h1 for main title, h2 for sections)
    - Add ARIA labels to all buttons and interactive elements
    - Ensure all images have descriptive alt text
    - Test keyboard navigation: Tab through all interactive elements, Enter to activate
    - Verify visible focus indicators on all interactive elements (outline in brand color)
    - Check color contrast: All text >= 4.5:1 for normal text, >= 3:1 for large text (WCAG 2.1 AA)
    - Ensure page is fully navigable with keyboard only (no mouse required)
    - _Requirements: 5.6, 11.1, 12.4, 12.5_

  - [~] 6.3 Optimize performance and SEO
    - Verify server-side rendering for initial page load
    - Ensure First Contentful Paint (FCP) < 2 seconds on 4G connection
    - Test image lazy loading (using Next.js Image component)
    - Verify no render-blocking CSS or JavaScript
    - Confirm meta tags in `<head>` for SEO (title, description, viewport, canonical)
    - Check that landing page is discoverable by search engines (no robots.txt exclusion)
    - _Requirements: 12.1, 12.2, 12.3_

  - [ ]* 6.4 Write property test for accessibility and responsive layout invariants
    - **Property 5: Responsive Layout Correctness**
    - **Property 7: Accessibility Invariant**
    - **Property 8: SEO and Metadata Correctness**
    - **Validates: Requirements 5.6, 7.1, 7.2, 7.3, 8.1, 9.1, 12.1, 12.4, 12.5**
    - Test that landing page renders without horizontal scrolling on all viewport widths
    - Test that all interactive elements are keyboard-navigable
    - Test that focus indicators are visible on all interactive elements
    - Test that SEO meta tags are present and correct

- [x] 7. Final checkpoint: Test and verify landing page

  Comprehensive testing to ensure all requirements are met.

  - Verify all tasks 1–6 are complete
  - Run full landing page in development environment (`npm run dev`)
  - Test on multiple devices/browsers: Chrome, Firefox, Safari (desktop, mobile, tablet)
  - Test authentication redirect on `/` with and without logged-in user
  - Test all CTA buttons navigate to correct destinations
  - Test responsive layout on 320px, 768px, 1024px, 1920px viewports
  - Test keyboard navigation (Tab through entire page)
  - Test with screen reader (NVDA or JAWS on Windows)
  - Verify no console errors or warnings
  - Confirm all tests pass (unit, property, integration)
  - Ask the user if they have questions or requested changes

---

## Notes

### Task Ordering and Dependencies

- **Task 1** must complete first (establishes routing and component structure)
- **Tasks 2, 3, 4, 5** can be done in parallel after Task 1 (independent sections)
- **Task 6** can start once Tasks 2–5 produce output (styling and accessibility pass)
- **Task 7** is the final validation checkpoint

### Testing Strategy

- **Unit Tests:** Test individual components in isolation (Hero, FeatureCard, Footer)
- **Property Tests:** Test universal behaviors (responsive layout, keyboard navigation, CTA routing)
- **Integration Tests:** Test full landing page rendering with all sections
- **Manual Testing:** Browser testing on multiple devices and screen sizes

### Optional Tasks (marked with `*`)

- Property and integration tests (1.3, 2.2, 3.4, 4.3, 5.4, 6.4) are optional for MVP
- Core implementation tasks (1.1, 1.2, 2.1, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3) are required

### File Changes Summary

| File | Change | Type |
|------|--------|------|
| `/app/page.tsx` | Modify to add auth check and render LandingPage | Modify |
| `/app/landing/LandingPage.tsx` | Create main container | Create |
| `/app/landing/HeroSection.tsx` | Create hero component | Create |
| `/app/landing/FeaturesSection.tsx` | Create features container | Create |
| `/app/landing/FeatureCard.tsx` | Create reusable card component | Create |
| `/app/landing/DashboardScreenshotSection.tsx` | Create screenshot component | Create |
| `/app/landing/FooterSection.tsx` | Create footer component | Create |
| `/public/images/dashboard-screenshot.png` | Add redacted dashboard image (placeholder) | Create |

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1", "5.1"] },
    { "id": 2, "tasks": ["2.3", "3.2", "3.3", "4.2", "5.2", "5.3"] },
    { "id": 3, "tasks": ["1.3", "2.2", "3.4", "4.3", "5.4", "6.1", "6.2", "6.3"] },
    { "id": 4, "tasks": ["6.4"] }
  ]
}
```

**Wave Explanation:**
- **Wave 0:** Establish routing and component structure (foundation)
- **Wave 1:** Create all section components in parallel
- **Wave 2:** Style and make responsive (can work independently on each section)
- **Wave 3:** Add testing, accessibility, and styling polish (can work in parallel)
- **Wave 4:** Final accessibility/SEO property tests (after all components complete)

---

## Completion Criteria

All tasks are complete when:
1. ✅ Root page (`/`) shows landing page for unauthenticated users
2. ✅ Authenticated users are redirected from `/` to `/dashboard`
3. ✅ Landing page displays on mobile (320px), tablet (768px), and desktop (1920px) without issues
4. ✅ All CTA buttons navigate to correct destinations
5. ✅ Page passes accessibility checks (keyboard navigation, screen reader, WCAG 2.1 AA)
6. ✅ All tests pass (unit, property, integration)
7. ✅ FCP < 2 seconds on 4G connection
8. ✅ SEO meta tags are correct in `<head>`
