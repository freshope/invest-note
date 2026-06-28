import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { CapacitorDeepLinkHandler } from "@/components/providers/CapacitorDeepLinkHandler";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppToaster } from "@/components/providers/AppToaster";
import { ForceUpdateGate } from "@/components/providers/ForceUpdateGate";
import { LiveUpdateReady } from "@/components/providers/LiveUpdateReady";
import { PageviewTracker } from "@/components/providers/PageviewTracker";
import { PostHogIdentifyBridge } from "@/components/providers/PostHogIdentifyBridge";
import { PostHogVersionBridge } from "@/components/providers/PostHogVersionBridge";
import { MySubmissionsPopupGate } from "@/components/providers/MySubmissionsPopupGate";
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
  themeColor: "#7C3AED",
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
    <html lang="ko" className={`${pretendard.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <ForceUpdateGate />
        <LiveUpdateReady />
        <AuthProvider>
          <CapacitorDeepLinkHandler />
          <PostHogIdentifyBridge />
          <PostHogVersionBridge />
          <PageviewTracker />
          <QueryProvider>
            {/* 토큰 준비(AuthProvider) + useQuery(QueryProvider) 모두 안에서 마운트. */}
            <MySubmissionsPopupGate />
            {children}
          </QueryProvider>
        </AuthProvider>
        <AppToaster />
      </body>
    </html>
  );
}
