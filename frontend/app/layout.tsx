import type { Metadata } from "next";

import "./globals.css";

import SupportWidget from "@/components/support-widget";

export const metadata: Metadata = {
  title: {
    default: "MarketingOS AI",
    template: "%s | MarketingOS AI",
  },
  description:
    "AI Marketing Operating System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body>{children}<SupportWidget /></body>
    </html>
  );
}
