"use client";

import React from "react";
import Link from "next/link";

interface FooterProps {
  // Add props as needed
}

interface FooterSection {
  title: string;
  links: Array<{
    label: string;
    href: string;
  }>;
}

export default function Footer({}: FooterProps) {
  const footerSections: FooterSection[] = [
    {
      title: "Product",
      links: [
        { label: "Features", href: "#features" },
        { label: "Pricing", href: "/pricing" },
        { label: "Security", href: "/security" },
        { label: "Documentation", href: "/docs" },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "About", href: "/about" },
        { label: "Blog", href: "/blog" },
        { label: "Contact", href: "/contact" },
        { label: "Careers", href: "/careers" },
      ],
    },
    {
      title: "Legal",
      links: [
        { label: "Privacy Policy", href: "/privacy" },
        { label: "Terms of Service", href: "/terms" },
        { label: "Cookies", href: "/cookies" },
        { label: "License", href: "/license" },
      ],
    },
  ];

  return (
    <footer
      className="w-full border-t border-slate-700 bg-slate-900 py-12 px-4"
      aria-label="Site footer"
    >
      <div className="max-w-6xl mx-auto">
        {/* Footer sections grid with semantic nav elements */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-8">
          {footerSections.map((section) => (
            <nav key={section.title} aria-label={`${section.title} links`}>
              <h3 className="
                text-white font-semibold text-sm uppercase tracking-wider mb-4
                focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded px-1
              ">
                {section.title}
              </h3>
              <ul className="space-y-3">
                {section.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="
                        text-slate-400
                        hover:text-slate-300
                        transition-colors duration-200
                        focus:outline-none focus:ring-2 focus:ring-indigo-500
                        focus:ring-offset-2 focus:ring-offset-slate-900
                        rounded px-1 py-1
                        inline-flex
                        min-h-[44px] items-center
                      "
                      aria-label={`${link.label} - ${section.title}`}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        {/* Divider */}
        <div className="border-t border-slate-700 pt-8 mt-8">
          {/* Copyright text */}
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-slate-400 text-sm">
              © 2024 DataGhost. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
