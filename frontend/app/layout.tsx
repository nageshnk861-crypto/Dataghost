import "./globals.css";
import type { Metadata } from "next";
import Providers from "./Providers";

export const metadata: Metadata = {
  title: "DataGhost — DLP Security Platform",
  description:
    "DataGhost is an AI-powered cloud-based Data Loss Prevention and Data Leakage Detection system. Monitor, classify, and block sensitive data exfiltration in real time.",
  keywords: "DLP, data loss prevention, data leakage detection, cybersecurity, SIEM",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="grid-pattern">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
