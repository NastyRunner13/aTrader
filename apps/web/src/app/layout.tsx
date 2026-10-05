import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "aTrader", template: "%s · aTrader" },
  description: "Evidence-linked research on NSE-listed companies.",
};

export const viewport: Viewport = {
  themeColor: "#0b0c0e",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
