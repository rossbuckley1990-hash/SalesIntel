import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./workspace.css";
import "./legacy-light.css";
import "./design-system.css";
import "./classic-light.css";
import "./fluid.css";

export const metadata: Metadata = {
  title: "SalesIntel",
  description: "Secure sales intelligence command centre for Mitie Fire & Security.",
};

export const viewport: Viewport = { themeColor: "#f7f6f3" };

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400..700&family=Geist:wght@400..700&family=Geist+Mono:wght@400..600&family=Instrument+Serif&display=swap" rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  );
}

