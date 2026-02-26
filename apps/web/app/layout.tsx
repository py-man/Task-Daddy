import "./globals.css";
import type { Metadata } from "next";
import { Toaster } from "sonner";
import { BackgroundLayer } from "@/components/background-layer";

export const metadata: Metadata = {
  title: "Task-Daddy",
  description: "Small tasks. Big momentum.",
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg"
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <BackgroundLayer />
        <div className="relative z-10">{children}</div>
        <Toaster richColors theme="dark" />
      </body>
    </html>
  );
}
