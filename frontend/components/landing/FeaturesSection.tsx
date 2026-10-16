"use client";

import React from "react";
import FeatureCard from "./FeatureCard";
import { Lock, AlertCircle, FileText } from "lucide-react";

interface FeaturesSectionProps {
  // Add props as needed
}

export default function FeaturesSection({}: FeaturesSectionProps) {
  const features = [
    {
      icon: <Lock size={32} className="text-blue-400" />,
      title: "Secret Detection",
      description:
        "Automatically identifies sensitive information like API keys, passwords, tokens, and credentials across your data—catching threats before they cause damage.",
    },
    {
      icon: <AlertCircle size={32} className="text-orange-400" />,
      title: "Risk Scoring & Classification",
      description:
        "AI-powered risk assessment assigns severity levels to data exposures, helping your team prioritize investigations and respond faster to high-risk incidents.",
    },
    {
      icon: <FileText size={32} className="text-green-400" />,
      title: "Audit Logging & Compliance",
      description:
        "Complete audit trail of all system activity and data interactions—meeting compliance requirements and providing forensic evidence for incident response.",
    },
  ];

  return (
    <section
      id="features"
      className="w-full py-20 px-4"
      aria-labelledby="features-heading"
    >
      <div className="max-w-6xl mx-auto">
        {/* Section heading */}
        <div className="mb-12 text-center">
          <h2
            id="features-heading"
            className="mb-4 text-4xl font-bold text-white"
          >
            Key Features
          </h2>
          <p className="text-lg text-slate-400">
            DataGhost DLP provides comprehensive data protection capabilities
          </p>
        </div>

        {/* Features grid - responsive layout */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
          {features.map((feature, index) => (
            <FeatureCard
              key={index}
              icon={feature.icon}
              title={feature.title}
              description={feature.description}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
