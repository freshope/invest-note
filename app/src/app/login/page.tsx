"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { signInWithOAuth } from "@/lib/auth";
import { useAuth } from "@/components/providers/AuthProvider";
import { OAUTH_BROWSER_FINISHED_EVENT } from "@/components/providers/CapacitorDeepLinkHandler";
import { getPlatform, isNativePlatform } from "@/lib/platform";
import { LEGAL_LINKS } from "@/lib/legal-links";

const KAKAO_BG = "#FEE500";
const KAKAO_FG = "#3C1E1E";
const AUTH_ERROR_MSG = "로그인 중 오류가 발생했습니다. 다시 시도해주세요.";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  );
}

function KakaoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path fillRule="evenodd" clipRule="evenodd" d="M9 0.75C4.444 0.75 0.75 3.611 0.75 7.125c0 2.26 1.444 4.247 3.625 5.393l-.923 3.433c-.082.305.27.548.53.365l4.01-2.67A10.6 10.6 0 0 0 9 13.5c4.556 0 8.25-2.861 8.25-6.375S13.556.75 9 .75z" fill={KAKAO_FG}/>
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M14.94 13.59c-.27.62-.59 1.19-.96 1.71-.51.72-.93 1.21-1.25 1.49-.5.46-1.04.7-1.62.71-.41 0-.91-.12-1.49-.36-.58-.24-1.11-.36-1.6-.36-.51 0-1.06.12-1.65.36-.59.24-1.06.37-1.42.38-.55.02-1.1-.22-1.66-.73-.34-.3-.78-.81-1.31-1.52-.57-.76-1.04-1.64-1.41-2.65C1.18 11.55 1 10.49 1 9.46c0-1.18.25-2.2.76-3.05.4-.69.93-1.23 1.59-1.62.66-.4 1.38-.6 2.15-.61.43 0 1.01.14 1.73.4.72.26 1.18.4 1.38.4.15 0 .66-.15 1.51-.45.81-.28 1.49-.4 2.06-.35 1.53.12 2.68.72 3.45 1.81-1.37.83-2.05 1.99-2.03 3.49.02 1.16.44 2.13 1.26 2.9.37.35.78.62 1.24.81-.1.29-.21.57-.32.84zM11.6 1.37c0 .88-.32 1.7-.96 2.46-.77.91-1.7 1.43-2.71 1.34A2.73 2.73 0 0 1 7.91 5c0-.85.36-1.75 1.01-2.5.32-.38.74-.69 1.24-.94.5-.25.97-.39 1.42-.41.01.07.02.15.02.22z" fill="currentColor"/>
    </svg>
  );
}

function LoginForm() {
  const searchParams = useSearchParams();
  const urlError = searchParams.get("error");
  const [pending, setPending] = useState<"google" | "kakao" | "apple" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Apple 심사 정책상 iOS에서만 Apple 로그인 노출 (hydration mismatch 방지를 위해 effect에서 판별)
  const [showApple, setShowApple] = useState(false);

  useEffect(() => {
    setShowApple(getPlatform() === "ios");
  }, []);

  // 네이티브에서 사용자가 인앱 브라우저를 수동으로 닫으면 pending 상태 해제
  useEffect(() => {
    const handler = () => setPending(null);
    window.addEventListener(OAUTH_BROWSER_FINISHED_EVENT, handler);
    return () => window.removeEventListener(OAUTH_BROWSER_FINISHED_EVENT, handler);
  }, []);

  async function handleSocialLogin(provider: "google" | "kakao" | "apple") {
    setError(null);
    setPending(provider);
    try {
      const native = isNativePlatform();
      const { url } = await signInWithOAuth(provider);

      if (native && url) {
        const { Browser } = await import("@capacitor/browser");
        await Browser.open({ url, presentationStyle: "popover" });
        // pending 해제는 딥링크 핸들러(성공)나 browserFinished 이벤트(취소)에서 처리
      }
    } catch {
      setError(AUTH_ERROR_MSG);
      setPending(null);
    }
  }

  return (
    <>
      <div className="flex flex-col gap-3">
        <button
          type="button"
          onClick={() => handleSocialLogin("google")}
          disabled={pending !== null}
          className="flex h-12 w-full items-center justify-center gap-3 rounded-2xl border border-border bg-background px-4 text-[15px] font-medium text-foreground transition-opacity disabled:opacity-50 hover:bg-muted"
        >
          <GoogleIcon />
          {pending === "google" ? "처리 중..." : "Google로 계속하기"}
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("kakao")}
          disabled={pending !== null}
          className="flex h-12 w-full items-center justify-center gap-3 rounded-2xl px-4 text-[15px] font-medium transition-opacity disabled:opacity-50"
          style={{ backgroundColor: KAKAO_BG, color: KAKAO_FG }}
        >
          <KakaoIcon />
          {pending === "kakao" ? "처리 중..." : "카카오로 계속하기"}
        </button>

        {showApple && (
          <button
            type="button"
            onClick={() => handleSocialLogin("apple")}
            disabled={pending !== null}
            className="flex h-12 w-full items-center justify-center gap-3 rounded-2xl bg-black px-4 text-[15px] font-medium text-white transition-opacity disabled:opacity-50 hover:opacity-90"
          >
            <AppleIcon />
            {pending === "apple" ? "처리 중..." : "Apple로 계속하기"}
          </button>
        )}
      </div>

      {(error ?? urlError) && (
        <p className="mt-4 rounded-xl bg-destructive/10 px-4 py-3 text-[13px] font-medium text-destructive text-center">
          {error ?? AUTH_ERROR_MSG}
        </p>
      )}
    </>
  );
}

export default function LoginPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-background px-5">
      <div className="w-full max-w-sm">
        <div className="mb-10 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            투자노트
          </h1>
          <p className="mt-2 text-[14px] text-muted-foreground">
            나만의 투자 기록 앱
          </p>
        </div>

        <Suspense>
          <LoginForm />
        </Suspense>

        <p className="mt-8 text-center text-[12px] text-muted-foreground">
          로그인 시{" "}
          <a
            href={LEGAL_LINKS.terms}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            서비스 이용약관
          </a>{" "}
          및{" "}
          <a
            href={LEGAL_LINKS.privacy}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            개인정보처리방침
          </a>
          에 동의하게 됩니다.
        </p>
      </div>
    </div>
  );
}
