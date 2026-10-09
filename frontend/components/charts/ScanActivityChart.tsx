"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

export interface ActivityDataPoint {
  date: string;
  scans: number;
  sensitive: number;
  blocked: number;
}

interface ScanActivityChartProps {
  data?: ActivityDataPoint[];
}

export default function ScanActivityChart({ data }: ScanActivityChartProps) {
  if (!data || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg"
        style={{ height: 220, background: "rgba(26,39,68,0.2)", color: "#475569" }}
      >
        <p className="text-sm">No activity data</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart
        data={data}
        margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(26,39,68,0.6)"
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tick={{ fill: "#475569", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#475569", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "#0f1729",
            border: "1px solid #1a2744",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "#94a3b8" }}
          itemStyle={{ color: "#e2e8f0" }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
        <Line
          type="monotone"
          dataKey="scans"
          name="Total Scans"
          stroke="#00d4ff"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#00d4ff" }}
        />
        <Line
          type="monotone"
          dataKey="sensitive"
          name="Sensitive"
          stroke="#ff9f0a"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#ff9f0a" }}
        />
        <Line
          type="monotone"
          dataKey="blocked"
          name="Blocked"
          stroke="#ff3b3b"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#ff3b3b" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
