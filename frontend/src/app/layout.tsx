import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MiSi - Mitie Sales Intelligence",
  description: "Secure sales intelligence command centre for Mitie Fire & Security.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

