import type { Metadata } from "next";

import "./globals.css";

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
      <body>{children}
        <footer className="border-t px-6 py-4 text-center text-sm text-neutral-500">
          <a
            href="/privacy"
            className="underline underline-offset-4 hover:text-neutral-900"
          >
            Privacy Policy
          </a>
        </footer>
      </body>
    </html>
  );
}
