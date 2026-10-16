"use client";

import React from "react";
import Link from "next/link";

/**
 * Landing page component displayed to unauthenticated users.
 * Shows key features and a call-to-action to log in.
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Navigation */}
      <nav className="border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div className="text-2xl font-bold text-white">DataGhost</div>
          <Link
            href="/login"
            className="inline-flex items-center justify-center px-6 py-2 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
          >
            Sign In
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-white mb-6">
            AI-Powered Data Loss Prevention
          </h1>
          <p className="text-xl text-slate-300 mb-8 max-w-3xl mx-auto">
            Detect, monitor, and prevent data exfiltration in real time with advanced machine learning and behavioral analysis.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/login"
              className="inline-flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
            >
              Get Started
            </Link>
            <Link
              href="#features"
              className="inline-flex items-center justify-center px-8 py-3 border border-slate-500 text-base font-medium rounded-md text-white hover:border-slate-400 transition-colors"
            >
              Learn More
            </Link>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition-colors">
            <div className="w-12 h-12 bg-indigo-600 rounded-lg mb-4 flex items-center justify-center">
              <span className="text-white font-bold">🔍</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Real-Time Detection</h3>
            <p className="text-slate-400">Monitor and detect sensitive data movements across your infrastructure instantly.</p>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition-colors">
            <div className="w-12 h-12 bg-indigo-600 rounded-lg mb-4 flex items-center justify-center">
              <span className="text-white font-bold">🛡️</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Intelligent Blocking</h3>
            <p className="text-slate-400">Automatically block and prevent unauthorized data exfiltration attempts.</p>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition-colors">
            <div className="w-12 h-12 bg-indigo-600 rounded-lg mb-4 flex items-center justify-center">
              <span className="text-white font-bold">📊</span>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Analytics & Reporting</h3>
            <p className="text-slate-400">Comprehensive insights and reporting on data protection events and incidents.</p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-slate-700 mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center text-slate-400">
          <p>&copy; 2024 DataGhost. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
}
