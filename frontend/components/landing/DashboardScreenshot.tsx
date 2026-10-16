"use client";

import React from "react";
import Image from "next/image";

interface DashboardScreenshotProps {
  // Add props as needed
}

/**
 * Dashboard Screenshot Section Component
 * 
 * Displays a professional screenshot showcase of the DataGhost dashboard.
 * Features:
 * - Responsive image display with proper scaling
 * - Rounded corners with subtle border and shadow
 * - Descriptive heading and caption
 * - Optimized image loading with Next.js Image component
 * - Full accessibility: semantic HTML, alt text, focus indicators, keyboard navigation
 */
export default function DashboardScreenshot({}: DashboardScreenshotProps) {
  const screenshotPath = "/images/dashboard-screenshot.png";

  return (
    <section
      className="w-full py-20 px-4 pb-24"
      aria-labelledby="dashboard-heading"
    >
      <div className="max-w-6xl mx-auto">
        {/* Section Heading with proper hierarchy and accessibility */}
        <div className="text-center mb-12">
          <h2
            id="dashboard-heading"
            className="
              text-3xl sm:text-4xl md:text-5xl
              font-bold text-white mb-4
              focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500
              focus:ring-offset-slate-900 rounded-lg px-2 py-1
            "
          >
            Comprehensive Dashboard
          </h2>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Gain complete visibility into your data protection infrastructure with our intuitive analytics platform.
          </p>
        </div>

        {/* Screenshot Container */}
        <div className="relative">
          {/* Outer wrapper for responsive sizing */}
          <div className="w-full flex justify-center">
            {/* Image wrapper with shadow and border */}
            <div className="w-full max-w-5xl">
              <div 
                className="
                  relative bg-slate-900 rounded-xl border border-slate-700
                  shadow-2xl overflow-hidden
                  focus-within:ring-2 focus-within:ring-indigo-500 focus-within:ring-offset-2 focus-within:ring-offset-slate-900
                "
                style={{
                  boxShadow: "0 0 60px rgba(99, 102, 241, 0.2)",
                }}
              >
                {/* Try to load the actual image, fallback to placeholder */}
                <div className="relative w-full" style={{ aspectRatio: "16 / 9" }}>
                  <Image
                    src={screenshotPath}
                    alt="DataGhost Dashboard interface showing real-time threat detection, device status monitoring, and security analytics"
                    fill
                    className="object-cover rounded-lg"
                    placeholder="blur"
                    blurDataURL="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 900'%3E%3Crect fill='%231e293b' width='1600' height='900'/%3E%3C/svg%3E"
                    priority
                    onError={() => {
                      // If image fails to load, it will show the blur placeholder
                    }}
                  />
                  
                  {/* Fallback placeholder if image is not found */}
                  <div className="
                    absolute inset-0 bg-gradient-to-br from-indigo-600/10 to-slate-700/10
                    rounded-lg flex items-center justify-center
                    pointer-events-none
                  ">
                    <div className="text-center text-slate-400">
                      <p className="text-sm">Dashboard Screenshot</p>
                      <p className="text-xs mt-2">
                        (Placeholder - add image at /public/images/dashboard-screenshot.png)
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Glow effect below screenshot */}
              <div 
                className="
                  mt-8 h-20 bg-gradient-to-b from-indigo-600/20 to-transparent
                  rounded-full filter blur-3xl -z-10 -mt-10
                "
                aria-hidden="true"
              />
            </div>
          </div>

          {/* Caption - descriptive text for image context */}
          <div className="text-center mt-8">
            <p className="text-slate-400 text-sm font-medium">
              DataGhost Dashboard - Real-time detection and analytics
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
