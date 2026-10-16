"use client";

import React from "react";
import Link from "next/link";

interface HeroSectionProps {
  // Add props as needed
}

/**
 * HeroSection component - displays main headline, subheadline, and CTA buttons
 * Features:
 * - Main headline: "AI-Powered Data Loss Prevention"
 * - Subheadline with key value proposition
 * - Two CTA buttons: "Get Started" (primary) and "Learn More" (secondary)
 * - Gradient background: slate-900 to slate-800
 * - Responsive typography: scales from 32px on mobile to 48px+ on desktop
 * - Buttons stack vertically on mobile, horizontally on desktop
 * - Hover effects and smooth transitions on buttons
 * - Proper spacing hierarchy using Tailwind spacing scale
 * - Full accessibility: semantic HTML, ARIA labels, keyboard navigation, focus indicators
 * 
 * @component
 * @example
 * <HeroSection />
 */
export default function HeroSection({}: HeroSectionProps) {
  return (
    <header className="w-full bg-gradient-to-b from-slate-900 to-slate-800 py-16 sm:py-20 md:py-24 lg:py-32 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto text-center">
        {/* Main headline with responsive typography and proper heading hierarchy */}
        <h1 className="
          text-3xl sm:text-4xl md:text-5xl lg:text-6xl
          font-bold text-white mb-6 leading-tight
          focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500
          focus:ring-offset-slate-900 rounded-lg px-2 py-1
        ">
          AI-Powered Data Loss Prevention
        </h1>

        {/* Subheadline with responsive typography */}
        <p className="
          text-base sm:text-lg md:text-xl lg:text-2xl
          text-slate-300 mb-8 sm:mb-10 md:mb-12
          max-w-2xl mx-auto leading-relaxed
        ">
          Detect, monitor, and prevent data exfiltration in real time
        </p>

        {/* CTA Buttons - stack vertically on mobile, horizontally on desktop */}
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-6 justify-center items-center">
          {/* Primary CTA Button - Get Started */}
          <Link
            href="/login"
            className="
              px-6 sm:px-8 py-3 sm:py-4
              bg-indigo-600
              text-white
              font-semibold
              rounded-lg
              hover:bg-indigo-700 hover:shadow-lg
              focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-slate-900
              active:bg-indigo-800
              transition-all duration-200
              inline-flex items-center justify-center
              whitespace-nowrap
              min-h-[44px]
            "
            aria-label="Get Started - Sign in to your account"
          >
            Get Started
          </Link>

          {/* Secondary CTA Button - Learn More */}
          <Link
            href="#features"
            className="
              px-6 sm:px-8 py-3 sm:py-4
              border-2 border-slate-400
              text-slate-300
              hover:text-white
              hover:border-white
              hover:shadow-lg
              font-semibold
              rounded-lg
              focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 focus:ring-offset-slate-900
              active:bg-slate-700
              transition-all duration-200
              inline-flex items-center justify-center
              whitespace-nowrap
              min-h-[44px]
            "
            aria-label="Learn More - Scroll to features section"
          >
            Learn More
          </Link>
        </div>
      </div>
    </header>
  );
}
