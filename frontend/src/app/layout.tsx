import type { Metadata } from "next";
import "./globals.css";
import "./workspace.css";
import "./legacy-light.css";
import "./design-system.css";
import "./classic-light.css";

export const metadata: Metadata = {
  title: "SalesIntel",
  description: "Secure sales intelligence command centre for Mitie Fire & Security.",
};

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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  );
}

