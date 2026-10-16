"use client";

import React from "react";

/**
 * Props for the FeatureCard component
 * @interface FeatureCardProps
 * @property {string} title - The title text displayed below the icon
 * @property {string} description - The description text in light gray
 * @property {React.ReactNode} [icon] - Optional React node for the icon (32px recommended size)
 * @property {string} [id] - Optional ID for accessibility linking
 */
interface FeatureCardProps {
  /** Title text displayed below the icon */
  title: string;
  /** Description text displayed below the title in light gray */
  description: string;
  /** Optional React node for the icon, typically a Lucide React icon */
  icon?: React.ReactNode;
  /** Optional ID for accessibility linking and aria-labelledby */
  id?: string;
}

/**
 * FeatureCard component displays a single feature with icon, title, and description
 * Features:
 * - Icon displayed in top-left of card (32px size for cards)
 * - Title with proper font weight and size
 * - Description text in light gray (text-slate-400)
 * - Subtle border (border-slate-700) and semi-transparent background (bg-slate-800 with 50% opacity)
 * - Hover effect: border brightens to slate-600, background opacity increases to 75%, box shadow added
 * - Smooth transitions using Tailwind duration classes
 * - Proper padding (24px) and spacing for visual hierarchy
 * - Full accessibility: semantic HTML, keyboard navigation, focus indicators
 * 
 * @component
 * @example
 * import { Lock } from 'lucide-react';
 * 
 * <FeatureCard
 *   icon={<Lock size={32} className="text-blue-400" />}
 *   title="Secret Detection"
 *   description="Automatically identifies sensitive information like API keys and passwords."
 *   id="secret-detection"
 * />
 */
export default function FeatureCard({
  title,
  description,
  icon,
  id,
}: FeatureCardProps): React.ReactElement {
  return (
    <article
      className="
        rounded-lg
        border border-slate-700
        bg-slate-800 bg-opacity-50
        p-6
        transition-all duration-300
        hover:border-slate-600
        hover:bg-opacity-75
        hover:shadow-lg
        focus-within:ring-2 focus-within:ring-indigo-500 focus-within:ring-offset-2 focus-within:ring-offset-slate-800
        outline-none
      "
      aria-labelledby={id ? `${id}-title` : undefined}
    >
      {/* Icon container - displays in top-left with proper spacing and role */}
      {icon && (
        <div className="mb-4 flex items-center justify-start" aria-hidden="false">
          {icon}
        </div>
      )}

      {/* Title - proper font weight, size for visual hierarchy, and accessibility */}
      <h3
        id={id ? `${id}-title` : undefined}
        className="
          mb-3
          text-lg
          font-semibold
          text-white
          focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded px-1
        "
      >
        {title}
      </h3>

      {/* Description - light gray color for secondary information */}
      <p className="text-slate-400 leading-relaxed text-base">
        {description}
      </p>
    </article>
  );
}
