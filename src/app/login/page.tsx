"use client";

import { useState, useActionState } from "react";
import { Button } from "@/components/base/Button";
import { signIn, signUp } from "@/app/auth/actions";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "signup">("login");

  const [loginState, loginAction, loginPending] = useActionState(signIn, undefined);
  const [signupState, signupAction, signupPending] = useActionState(signUp, undefined);

  const isLogin = mode === "login";
  const state = isLogin ? loginState : signupState;
  const action = isLogin ? loginAction : signupAction;
  const isPending = isLogin ? loginPending : signupPending;

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        {/* 로고 */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            투자노트
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            나만의 투자 기록 앱
          </p>
        </div>

        {/* 탭 */}
        <div className="mb-6 flex rounded-lg bg-muted p-1">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-all ${
              isLogin
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground"
            }`}
          >
            로그인
          </button>
          <button
            type="button"
            onClick={() => setMode("signup")}
            className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-all ${
              !isLogin
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground"
            }`}
          >
            회원가입
          </button>
        </div>

        {/* 폼 */}
        <form action={action} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-sm font-medium text-foreground">
              이메일
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="name@example.com"
              className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm font-medium text-foreground">
              비밀번호
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete={isLogin ? "current-password" : "new-password"}
              placeholder="비밀번호를 입력하세요"
              minLength={6}
              className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            />
          </div>

          {/* 에러/성공 메시지 */}
          {state?.error && (
            <p className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {state.error}
            </p>
          )}
          {state?.success && (
            <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
              {state.success}
            </p>
          )}

          <Button
            type="submit"
            disabled={isPending}
            className="h-10 w-full rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-60"
          >
            {isPending ? "처리 중..." : isLogin ? "로그인" : "회원가입"}
          </Button>
        </form>
      </div>
    </div>
  );
}
