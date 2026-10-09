import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "dg-bg": "#0a0f1e",
        "dg-card": "#0f1729",
        "dg-border": "#1a2744",
        "dg-cyan": "#00d4ff",
        "dg-danger": "#ff3b3b",
        "dg-warning": "#ff9f0a",
        "dg-success": "#34d058",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
