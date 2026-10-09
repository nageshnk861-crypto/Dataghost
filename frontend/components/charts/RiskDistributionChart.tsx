"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export interface RiskSegment {
  name: string;
  value: number;
  color: string;
}

interface RiskDistributionChartProps {
  data?: RiskSegment[];
}

export default function RiskDistributionChart({ data }: RiskDistributionChartProps) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg"
        style={{ height: 220, background: "rgba(26,39,68,0.2)", color: "#475569" }}
      >
        <p className="text-sm">No risk data</p>
      </div>
    );
  }

  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="flex flex-col items-center">
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={3}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#0f1729",
              border: "1px solid #1a2744",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#94a3b8" }}
            formatter={(value: number, name: string) => [
              `${value} (${((value / total) * 100).toFixed(1)}%)`,
              name,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Custom legend */}
      <div className="w-full mt-2 space-y-1.5">
        {data.map((d) => (
          <div key={d.name} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ background: d.color }}
              />
              <span style={{ color: "#94a3b8" }}>{d.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono" style={{ color: d.color }}>
                {d.value.toLocaleString()}
              </span>
              <span style={{ color: "#334155" }}>
                ({((d.value / total) * 100).toFixed(0)}%)
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
