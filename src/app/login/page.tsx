"use client";

import { useState, useActionState } from "react";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
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
    <div className="flex min-h-svh flex-col items-center justify-center bg-background px-5">
      <div className="w-full max-w-sm">
        {/* 로고 */}
        <div className="mb-10 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            투자노트
          </h1>
          <p className="mt-2 text-[14px] text-muted-foreground">
            나만의 투자 기록 앱
          </p>
        </div>

        {/* 탭 */}
        <div className="mb-6 flex rounded-2xl bg-muted p-1">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`flex-1 rounded-xl py-2.5 text-[14px] font-semibold transition-all ${
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
            className={`flex-1 rounded-xl py-2.5 text-[14px] font-semibold transition-all ${
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
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">이메일</Label>
            <Input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="name@example.com"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="password">비밀번호</Label>
            <Input
              id="password"
              name="password"
              type="password"
              required
              autoComplete={isLogin ? "current-password" : "new-password"}
              placeholder="비밀번호를 입력하세요"
              minLength={6}
            />
          </div>

          {/* 에러/성공 메시지 */}
          {state?.error && (
            <p className="rounded-xl bg-destructive/10 px-4 py-3 text-[13px] font-medium text-destructive">
              {state.error}
            </p>
          )}
          {state?.success && (
            <p className="rounded-xl bg-green-50 px-4 py-3 text-[13px] font-medium text-green-700">
              {state.success}
            </p>
          )}

          <Button
            type="submit"
            size="xl"
            disabled={isPending}
            className="w-full mt-2"
          >
            {isPending ? "처리 중..." : isLogin ? "로그인" : "회원가입"}
          </Button>
        </form>
      </div>
    </div>
  );
}
