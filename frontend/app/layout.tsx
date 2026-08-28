import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "MarketingOS AI",
    template: "%s | MarketingOS AI",
  },
  description:
    "為中文市場商家打造的品牌、AI 內容與社群發布工作流。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body>{children}
        <footer className="site-footer">
          <span>© MarketingOS AI</span>
          <a href="/pricing">方案價格</a>
          <a
            href="/privacy"
          >
            Privacy Policy
          </a>
        </footer>
      </body>
    </html>
  );
}
