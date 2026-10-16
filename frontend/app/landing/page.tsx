"use client";

import React from "react";
import HeroSection from "@/components/landing/HeroSection";
import FeaturesSection from "@/components/landing/FeaturesSection";
import DashboardScreenshot from "@/components/landing/DashboardScreenshot";
import Footer from "@/components/landing/Footer";

export default function LandingPage() {
  return (
    <>
      {/* Skip to main content link - visible on focus for keyboard navigation */}
      <a
        href="#main-content"
        className="
          absolute top-0 left-0
          -translate-y-full
          focus:translate-y-0
          focus:z-50
          px-4 py-2
          bg-indigo-600
          text-white
          font-semibold
          rounded-b-lg
          transition-transform duration-200
          focus:outline-none
          focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500
        "
      >
        Skip to main content
      </a>

      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <HeroSection />
        <FeaturesSection />
        {/* Main content section for skip link */}
        <main id="main-content">
          <DashboardScreenshot />
        </main>
        <Footer />
      </div>
    </>
  );
}
