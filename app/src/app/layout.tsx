import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { AndroidBackHandler } from "@/components/providers/AndroidBackHandler";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { CapacitorDeepLinkHandler } from "@/components/providers/CapacitorDeepLinkHandler";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { ThemedToaster } from "@/components/providers/ThemedToaster";
import { StatusBarThemeSync } from "@/components/providers/StatusBarThemeSync";
import { ForceUpdateGate } from "@/components/providers/ForceUpdateGate";
import { LiveUpdateReady } from "@/components/providers/LiveUpdateReady";
import { PageviewTracker } from "@/components/providers/PageviewTracker";
import { PostHogIdentifyBridge } from "@/components/providers/PostHogIdentifyBridge";
import { PostHogVersionBridge } from "@/components/providers/PostHogVersionBridge";
import { PushRegistration } from "@/components/providers/PushRegistration";
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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#17171C" },
  ],
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
    <html
      lang="ko"
      className={`${pretendard.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <StatusBarThemeSync />
          <ForceUpdateGate />
          {/* AuthProvider 밖 — 로그인 화면에서도 백버튼 종료가 동작해야 한다. */}
          <AndroidBackHandler />
          <LiveUpdateReady />
          <AuthProvider>
            <CapacitorDeepLinkHandler />
            <PushRegistration />
            <PostHogIdentifyBridge />
            <PostHogVersionBridge />
            <PageviewTracker />
            <QueryProvider>
              {children}
            </QueryProvider>
          </AuthProvider>
          <ThemedToaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
