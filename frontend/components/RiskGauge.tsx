"use client";

interface RiskGaugeProps {
  score: number;
  size?: number;
}

function scoreColor(score: number): string {
  if (score >= 80) return "#ff3b3b";
  if (score >= 60) return "#ff6b35";
  if (score >= 30) return "#ff9f0a";
  return "#34d058";
}

export default function RiskGauge({ score, size = 200 }: RiskGaugeProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = (size * 0.38);
  const strokeW = size * 0.07;

  // Semicircle from 180° to 0° (left to right)
  // SVG arc from (cx - r, cy) to (cx + r, cy) going through top
  const startX = cx - r;
  const startY = cy;
  const endX = cx + r;
  const endY = cy;

  const arcPath = `M ${startX} ${startY} A ${r} ${r} 0 0 1 ${endX} ${endY}`;

  // Total arc length for a semicircle = π * r
  const totalLen = Math.PI * r;
  const filledLen = (score / 100) * totalLen;
  const gapLen = totalLen - filledLen;

  const color = scoreColor(score);

  const label =
    score >= 80 ? "CRITICAL" : score >= 60 ? "HIGH" : score >= 30 ? "MEDIUM" : "LOW";

  return (
    <div
      className="flex flex-col items-center"
      style={{ width: size, userSelect: "none" }}
    >
      <svg
        width={size}
        height={size * 0.6}
        viewBox={`0 0 ${size} ${size * 0.6}`}
        style={{ overflow: "visible" }}
      >
        {/* Background track */}
        <path
          d={arcPath}
          fill="none"
          stroke="#1a2744"
          strokeWidth={strokeW}
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d={arcPath}
          fill="none"
          stroke={color}
          strokeWidth={strokeW}
          strokeLinecap="round"
          strokeDasharray={`${filledLen} ${gapLen + 1}`}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        {/* Score text */}
        <text
          x={cx}
          y={cy * 0.85}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={color}
          fontSize={size * 0.17}
          fontWeight="700"
          fontFamily="Inter, system-ui, sans-serif"
        >
          {score}
        </text>
        <text
          x={cx}
          y={cy * 0.85 + size * 0.1}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#94a3b8"
          fontSize={size * 0.065}
          fontFamily="Inter, system-ui, sans-serif"
        >
          / 100
        </text>
        {/* LOW label */}
        <text
          x={startX + strokeW / 2}
          y={cy + strokeW * 0.8}
          textAnchor="start"
          fill="#475569"
          fontSize={size * 0.055}
          fontFamily="Inter, system-ui, sans-serif"
        >
          LOW
        </text>
        {/* CRITICAL label */}
        <text
          x={endX - strokeW / 2}
          y={cy + strokeW * 0.8}
          textAnchor="end"
          fill="#475569"
          fontSize={size * 0.055}
          fontFamily="Inter, system-ui, sans-serif"
        >
          CRITICAL
        </text>
      </svg>
      {/* Severity label */}
      <span
        className="text-xs font-bold px-3 py-1 rounded-full mt-1"
        style={{
          background: `${color}15`,
          color,
          border: `1px solid ${color}30`,
        }}
      >
        {label}
      </span>
    </div>
  );
}
