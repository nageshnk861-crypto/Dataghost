# Design Document: Public Landing Page

## Introduction

The public landing page is a single-page, scroll-based marketing interface that introduces DataGhost DLP to unauthenticated users. Built with Next.js 14, TypeScript, Tailwind CSS, and Lucide React, it seamlessly integrates with the existing DataGhost frontend while serving as the primary entry point for new visitors. The page is fully responsive (320px to 1920px+) and includes strategic call-to-action buttons to drive user acquisition and engagement.

## Architecture Overview

### Component Hierarchy

```
LandingPage (page.tsx)
├── Header / Navigation
│   └── Logo + CTA buttons (Sign In, Try Demo)
├── HeroSection
│   ├── Headline
│   ├── Subheading
│   └── CTA Buttons
├── FeaturesSection
│   ├── FeatureCard 1 (Secret Detection)
│   ├── FeatureCard 2 (Risk Scoring)
│   └── FeatureCard 3 (Audit Logging)
├── DashboardScreenshotSection
│   └── Redacted Dashboard Image + Description
├── FooterSection
│   ├── Navigation Links
│   ├── Legal Links
│   └── Copyright Info
└── Hidden: Authenticated Redirect Logic
```

### Data Flow

1. **User navigates to `/`**
2. **Root page (`/app/page.tsx`) checks authentication status**
   - If authenticated: Redirect to `/dashboard`
   - If unauthenticated: Render LandingPage component
3. **LandingPage renders**
   - Static content (no API calls required)
   - All CTAs link to `/login` or sign-up flow
4. **User clicks CTA**
   - Sign In: Navigate to `/login` (existing route)
   - Try Demo: Navigate to sign-up flow

## Component Specifications

### 1. Root Page Component (`/app/page.tsx`)

**Purpose:** Lightweight router that redirects authenticated users to `/dashboard` and renders the landing page for unauthenticated users.

**Implementation Notes:**
- Use Next.js `redirect()` for authenticated users (server-side)
- Check authentication via NextAuth session or Firebase auth context
- Landing page renders server-side for SEO and performance

```typescript
// Pseudocode
export default function RootPage() {
  const session = useSession() || auth context
  
  if (session?.user) {
    redirect("/dashboard")
  }
  
  return <LandingPage />
}
```

---

### 2. Landing Page Component (`/app/landing/LandingPage.tsx`)

**Purpose:** Main container for all landing page sections.

**Key Features:**
- Single-page scroll layout
- Semantic HTML structure for accessibility
- Full-width with max-width constraint (1400px) for desktop
- Responsive padding and spacing

**Layout:**
- Mobile (320px): Full width, stacked sections
- Tablet (768px): Optimized 2-column layouts where applicable
- Desktop (1024px+): 3-column feature grid, full-width dashboard screenshot

---

### 3. Header / Navigation Component

**Purpose:** Sticky or fixed header with logo and CTA buttons.

**Elements:**
- DataGhost logo (left-aligned or centered)
- "Sign In" button (secondary style, right-aligned)
- "Try Demo" button (primary style, right-aligned)

**Responsive Behavior:**
- Mobile: Logo takes full width on top row; buttons stack or condense
- Desktop: Logo on left, buttons on right in a single row

**Accessibility:**
- Logo links to `/` (landing page root)
- Buttons have proper ARIA labels
- Keyboard navigation supports Tab through buttons

---

### 4. Hero Section Component

**Purpose:** Above-the-fold area that captures attention and communicates value proposition.

**Elements:**
- **Headline:** "Detect, Classify, and Prevent Data Loss with AI-Powered DLP"
  - Font: Large (48px desktop, 32px mobile), bold, brand color or high contrast
  - Max 2 lines on desktop, may wrap on mobile
  
- **Subheading:** "DataGhost detects sensitive information in real-time, scores risk levels, and provides audit trails for compliance—all without manual configuration."
  - Font: Medium (18px desktop, 16px mobile), regular weight, secondary text color
  
- **Primary CTA:** "Sign In" button
  - Style: Primary (bold, brand color background, white text)
  - Action: Navigate to `/login`
  
- **Secondary CTA:** "Try Demo" button
  - Style: Secondary (outline or ghost button, border, text color)
  - Action: Navigate to sign-up flow

**Layout:**
- Desktop: Centered or left-aligned headline with text and buttons below
- Mobile: Full-width headline, buttons stack vertically (full-width or side-by-side)
- Minimum height: 60vh on desktop, 50vh on mobile

**Background:**
- Subtle gradient or solid color background
- May include a decorative element or icon (optional)
- No background image to maintain performance

---

### 5. Features Section Component

**Purpose:** Showcase 3 core capabilities of DataGhost DLP.

**Feature Cards:**

#### Feature Card 1: Secret Detection
- **Icon:** Lock or key icon (Lucide React)
- **Title:** "Secret Detection"
- **Description:** "Automatically identifies sensitive information like API keys, passwords, tokens, and credentials across your data—catching threats before they cause damage."
- **Visual:** Icon at top, text below

#### Feature Card 2: Risk Scoring
- **Icon:** Gauge or alert icon (Lucide React)
- **Title:** "Risk Scoring & Classification"
- **Description:** "AI-powered risk assessment assigns severity levels to data exposures, helping your team prioritize investigations and respond faster to high-risk incidents."
- **Visual:** Icon at top, text below

#### Feature Card 3: Audit Logging
- **Icon:** Log or document icon (Lucide React)
- **Title:** "Audit Logging & Compliance"
- **Description:** "Complete audit trail of all system activity and data interactions—meeting compliance requirements and providing forensic evidence for incident response."
- **Visual:** Icon at top, text below

**Card Layout:**
- Each card: Icon (60x60px), title (20px bold), description (14px regular)
- Padding: 24px internal spacing
- Border: Subtle border or shadow for separation

**Grid Layout:**
- Desktop (1024px+): 3-column grid with equal spacing
- Tablet (768px–1023px): 2-column or flex layout
- Mobile (< 768px): Single column, full-width cards stacked vertically
- Gap between cards: 24px (consistent with design system)

**Responsive Typography:**
- Desktop: Title 20px, Description 14px
- Mobile: Title 18px, Description 14px (maintain readability)

---

### 6. Dashboard Screenshot Section

**Purpose:** Visual proof of the dashboard interface to give visitors confidence.

**Elements:**
- **Title/Heading:** "See the DataGhost Dashboard in Action"
- **Description:** Short text describing what the screenshot shows (e.g., "Real-time threat detection with AI-powered risk scoring")
- **Image:** Redacted dashboard screenshot (PNG or JPG)
  - Resolution: 1920x1080 (or aspect ratio-locked responsive image)
  - File path: `/public/images/dashboard-screenshot.png` (to be added during implementation)
  - Alt text: "DataGhost dashboard showing threat detection, risk metrics, and audit logs"

**Layout:**
- Desktop: Image takes 80–90% of viewport width with padding
- Tablet: Image takes full width with side padding (16px–24px)
- Mobile: Image takes full width with top/bottom padding (16px), slightly reduced shadow/border for mobile

**Image Optimization:**
- Use `Next.js Image` component for automatic optimization and responsive loading
- Implement lazy loading for performance (image loads when in viewport)
- Provide srcSet for different resolutions (mobile, tablet, desktop)

---

### 7. Footer Component

**Purpose:** Provide additional navigation and legal information.

**Elements:**
- **Navigation Links:** (left or center column)
  - "Contact Us"
  - "Support / Help"
  - "Documentation" (optional)
  
- **Legal Links:** (center or right column)
  - "Privacy Policy"
  - "Terms of Service"
  - "Security" (optional)
  
- **Copyright Notice:** "© 2025 DataGhost. All rights reserved." or similar
- **Social Links:** (optional) GitHub, Twitter, LinkedIn icons

**Layout:**
- Desktop: Multi-column layout (3–4 columns) with text and links
- Tablet: 2-column layout
- Mobile: Single column, links stacked vertically

**Styling:**
- Background: Subtle dark or light background (consistent with app dark mode/light mode)
- Text color: Secondary text color (muted)
- Link hover states: Underline or color change for accessibility
- Padding: 48px top/bottom, 24px left/right (mobile: 24px all)

---

## Responsive Design Specifications

### Breakpoints

| Device | Viewport Width | Layout | Feature Cards |
|--------|---|---|---|
| Mobile | 320px–480px | Single column, full-width | Stacked vertically |
| Mobile (Large) | 481px–768px | Single column, optimized padding | Stacked or 2-column |
| Tablet | 768px–1024px | 1–2 columns with more breathing room | 2-column grid |
| Desktop | 1024px–1440px | Multi-column with max-width constraint | 3-column grid |
| Desktop (XL) | 1440px+ | Max-width 1400px, centered | 3-column grid |

### Typography Scale

| Size | Usage | Mobile | Tablet | Desktop |
|---|---|---|---|---|
| Headline | Hero title | 32px | 40px | 48px |
| Subheading | Hero subtitle, section titles | 16px | 18px | 20px |
| Card Title | Feature card titles | 18px | 18px | 20px |
| Body | Descriptions, footer text | 14px | 14px | 16px |
| Small | Footer copyright, meta info | 12px | 12px | 14px |

### Spacing Scale

| Spacing | Usage |
|---|---|
| 8px | Small gaps, micro spacing |
| 16px | Small padding, vertical spacing |
| 24px | Standard padding, component gaps |
| 32px | Section spacing |
| 48px | Large section gaps, footer padding |
| 64px | Hero section spacing |

---

## Styling Guidelines

### Color Palette

- **Primary Brand Color:** Use existing DataGhost primary color (likely blue or similar)
- **Secondary Color:** Use existing secondary color for CTAs and highlights
- **Background:** Light or dark mode consistent with existing app
- **Text:** Primary (main text), Secondary (muted text), Tertiary (very muted)
- **Borders:** Subtle borders for card separation
- **Shadows:** Subtle shadows for depth and hierarchy

### Typography

- **Font Family:** Inter (existing, via @link)
- **Font Weights:** 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Line Height:** 1.5 for body, 1.2 for headings

### Interactive Elements

- **Button Styles:**
  - Primary: Solid background (brand color), white text, 12px horizontal padding, 8px vertical padding, 6px border-radius
  - Secondary: Outline (border only, no fill), text color = brand, 12px horizontal padding, 8px vertical padding, 6px border-radius
  - Hover: Opacity change or slight color shift, cursor pointer
  - Focus: Ring or outline for keyboard users (WCAG 2.1 AA compliant)
  
- **Links:** Color with underline on hover, focus ring for keyboard users

### Icons

- **Library:** Lucide React
- **Size:** 24px for inline, 48px–64px for hero, 32px for cards
- **Color:** Inherit from text or brand color
- **Stroke Width:** Default (2px)

---

## Accessibility Requirements

1. **Semantic HTML:** Use proper heading hierarchy (h1 for main title, h2 for sections, h3 for subsections)
2. **ARIA Labels:** All interactive elements (buttons, links) have descriptive labels or aria-label attributes
3. **Color Contrast:** All text meets WCAG 2.1 AA contrast ratio (4.5:1 for normal text, 3:1 for large text)
4. **Keyboard Navigation:** All elements navigable via Tab, Shift+Tab, Enter, and arrow keys
5. **Focus Indicators:** Visible focus rings on all interactive elements (not removed, outlined in contrast color)
6. **Image Alt Text:** All images have descriptive alt text
7. **Screen Reader Support:** Page structure and content fully navigable with screen readers
8. **Motion:** No auto-playing animations; respect prefers-reduced-motion media query

---

## Performance Considerations

1. **Server-Side Rendering (SSR):** Render landing page on server for SEO and initial performance
2. **Image Optimization:** Use Next.js `Image` component with automatic format negotiation, lazy loading, and responsive srcSet
3. **Code Splitting:** Load landing page component only on `/` route
4. **Minimal Dependencies:** Use Tailwind CSS (already included) and Lucide React (already included)
5. **Static Content:** No dynamic data fetches required; all content is static
6. **CSS-in-JS:** Avoid runtime CSS-in-JS; use Tailwind's compiled CSS

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Unauthenticated Access Invariant

For any unauthenticated user, when they navigate to `/`, the landing page SHALL render without requiring authentication or redirecting to the login page.

**Validates: Requirements 1.1, 1.3**

### Property 2: Authenticated Redirect Invariant

For any authenticated user, when they navigate to `/`, the system SHALL redirect them to `/dashboard` and SHALL NOT render the landing page.

**Validates: Requirements 1.2, 10.3**

### Property 3: CTA Navigation Correctness

For any click event on the "Sign In" button, the system SHALL navigate to `/login`. For any click event on the "Try Demo" button, the system SHALL navigate to the sign-up flow.

**Validates: Requirements 2.5, 2.6, 5.3, 5.4**

### Property 4: Feature Cards Rendering

For any viewport width, the landing page SHALL render at least 3 feature cards with titles, descriptions, and icons. On mobile (< 768px), cards SHALL display in a vertical stack. On desktop (>= 1024px), cards SHALL display in a 3-column grid.

**Validates: Requirements 3.1, 3.2, 3.3, 3.5, 3.6**

### Property 5: Responsive Layout Correctness

For any viewport width between 320px and 1920px, the landing page SHALL render without horizontal scrolling and all content SHALL remain readable and accessible. Text SHALL not be smaller than 12px on any viewport.

**Validates: Requirements 7.1, 7.2, 7.3, 8.1, 9.1, 9.4**

### Property 6: Dashboard Screenshot Responsiveness

For any viewport width, the dashboard screenshot image SHALL display at an appropriate scale and aspect ratio. On mobile, the image SHALL not exceed the viewport width. On desktop, the image SHALL not exceed 90% of the viewport width.

**Validates: Requirements 4.4, 4.5, 9.5**

### Property 7: Accessibility Invariant

For any interactive element on the landing page (button, link), keyboard users SHALL be able to navigate to it using the Tab key, see a visible focus indicator, and activate it using the Enter key.

**Validates: Requirements 5.6, 12.4, 12.5**

### Property 8: SEO and Metadata Correctness

When the landing page is rendered, the `<head>` element SHALL include proper meta tags (title, description, viewport, canonical) for search engine indexing and social media sharing.

**Validates: Requirement 12.1**

---

## Implementation Strategy

### Phase 1: Component Setup
1. Create `/app/landing/` directory
2. Create `LandingPage.tsx` main component
3. Create individual section components (Hero, Features, DashboardScreenshot, Footer)
4. Update `/app/page.tsx` to check auth and render or redirect

### Phase 2: Styling and Responsiveness
1. Style components using Tailwind CSS with responsive breakpoints
2. Implement responsive typography and spacing
3. Add Lucide React icons

### Phase 3: Accessibility and Polish
1. Add ARIA labels and semantic HTML
2. Implement keyboard navigation
3. Test with screen readers
4. Add focus states and color contrast checks

### Phase 4: Testing
1. Write unit tests for routing logic
2. Write property-based tests for responsive layout
3. Test authentication redirect
4. Integration test unauthenticated access

### Phase 5: Deployment
1. Add redacted dashboard screenshot to `/public/images/`
2. Deploy to production
3. Monitor performance metrics

---

## File Structure

```
frontend/
├── app/
│   ├── page.tsx                 # Root page with auth check
│   ├── landing/
│   │   ├── LandingPage.tsx      # Main landing page component
│   │   ├── HeroSection.tsx
│   │   ├── FeaturesSection.tsx
│   │   ├── FeatureCard.tsx
│   │   ├── DashboardScreenshotSection.tsx
│   │   └── FooterSection.tsx
│   └── ...existing routes...
├── public/
│   └── images/
│       └── dashboard-screenshot.png  # (Add during implementation)
└── ...
```

---

## Notes

- All components use TypeScript for type safety
- Components integrate seamlessly with existing Tailwind CSS configuration
- No additional dependencies required beyond existing stack (Next.js, React, Tailwind, Lucide)
- Landing page is fully self-contained and does not depend on authenticated API routes
- CTA buttons link to existing routes (`/login` and sign-up flow)
