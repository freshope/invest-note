import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { CapacitorDeepLinkHandler } from "@/components/providers/CapacitorDeepLinkHandler";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { ThemedToaster } from "@/components/providers/ThemedToaster";
import "./globals.css";

const pretendard = localFont({
  src: "./fonts/PretendardVariable.woff2",
  display: "swap",
  weight: "45 920",
  variable: "--font-pretendard",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export const metadata: Metadata = {
  title: "투자노트",
  description: "나만의 투자 기록 앱",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${pretendard.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <AuthProvider>
            <CapacitorDeepLinkHandler />
            <QueryProvider>{children}</QueryProvider>
          </AuthProvider>
          <ThemedToaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
