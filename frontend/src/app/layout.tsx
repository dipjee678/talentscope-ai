import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "@/styles/globals.css";
import { AppProviders } from "@/components/providers";
import { ServerWakeBanner } from "@/components/server-wake-banner";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

export const metadata: Metadata = {
  title: "TalentScope AI — Find jobs that fit your CV",
  description:
    "Upload your CV, choose your countries, and get verified job openings ranked by how well they fit — with a clear explanation for every score."
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8fafc" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1020" }
  ]
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.variable}`} suppressHydrationWarning>
      <body className="font-sans">
        <AppProviders>{children}</AppProviders>
        <ServerWakeBanner />
      </body>
    </html>
  );
}
