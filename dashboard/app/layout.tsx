import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "wayfinder dashboard",
  description: "Monitoring shell for verifier-backed codebase onboarding runs.",
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
