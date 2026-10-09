import React from "react";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}

export default function StatCard({ title, value, icon, color, subtitle }: StatCardProps) {
  return (
    <div
      className="relative rounded-xl p-5 flex flex-col justify-between overflow-hidden transition-all duration-200 hover:-translate-y-0.5"
      style={{
        background: "linear-gradient(135deg, #0f1729 0%, #0a1020 100%)",
        border: "1px solid #1a2744",
        borderLeft: `3px solid ${color}`,
        boxShadow: `0 4px 20px rgba(0,0,0,0.3), inset 0 0 60px ${color}08`,
      }}
    >
      {/* Icon */}
      <div className="flex items-start justify-between">
        <div>
          <p
            className="text-xs font-semibold uppercase tracking-widest mb-1"
            style={{ color: "#94a3b8" }}
          >
            {title}
          </p>
          <p
            className="text-3xl font-bold leading-none"
            style={{ color }}
          >
            {value}
          </p>
          {subtitle && (
            <p className="text-xs mt-1.5" style={{ color: "#475569" }}>
              {subtitle}
            </p>
          )}
        </div>
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{
            background: `${color}15`,
            border: `1px solid ${color}30`,
            color,
          }}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}
