"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { useAuth } from "@/components/providers/AuthProvider";

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

function LoginForm() {
  const searchParams = useSearchParams();
  const urlError = searchParams.get("error");
  const [pending, setPending] = useState<"google" | "kakao" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSocialLogin(provider: "google" | "kakao") {
    setError(null);
    setPending(provider);
    try {
      const supabase = createClient();
      const redirectTo = `${window.location.origin}/auth/callback`;
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo },
      });
      if (error) throw error;
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
          로그인 시 서비스 이용약관 및 개인정보처리방침에 동의하게 됩니다.
        </p>
      </div>
    </div>
  );
}
