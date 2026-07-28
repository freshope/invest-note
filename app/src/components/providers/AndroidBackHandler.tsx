"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import { getPlatform } from "@/lib/platform";
import { runTopBackHandler } from "@/lib/back-handler";
import { useUpdateRequired } from "@/hooks/useUpdateRequired";

/** 백버튼 두 번으로 종료. 첫 입력 후 이 시간 안에 다시 눌러야 한다. */
const EXIT_CONFIRM_MS = 2000;

/** radix DismissableLayer 가 Escape 로 닫는 z-[200] 레이어(Dialog/Drawer/Select). */
const DISMISSABLE_SELECTOR =
  '[data-state="open"][role="dialog"], [data-state="open"][role="alertdialog"], [data-state="open"][role="listbox"]';

function closeTopDismissable(): boolean {
  if (!document.querySelector(DISMISSABLE_SELECTOR)) return false;
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  return true;
}

/**
 * Android 하드웨어 백버튼 처리.
 *
 * @capacitor/app 의 기본 핸들러는 백프레스를 항상 소비하면서 웹뷰 히스토리가 없을 때
 * activity 를 finish 하지 않아, 루트에서 백버튼을 눌러도 앱이 종료되지 않는다.
 * 게다가 탭 전환이 `<Link>`(history push) 라 홈에서도 canGoBack 이 계속 true 다.
 * 여기서 리스너를 등록하면 그 기본 동작이 꺼지므로 아래 체인 전체를 직접 소유한다:
 *   강제 업데이트(무시) → radix 레이어 → FullScreenPanel → 히스토리 → 두 번 눌러 종료.
 */
export function AndroidBackHandler() {
  const pathname = usePathname();
  const required = useUpdateRequired();

  // 리스너는 한 번만 등록하고 최신 값은 ref 로 읽는다(재등록 중 백프레스 유실 방지).
  const pathnameRef = useRef(pathname);
  const requiredRef = useRef(required);
  useEffect(() => {
    pathnameRef.current = pathname;
    requiredRef.current = required;
  });

  useEffect(() => {
    if (getPlatform() !== "android") return;
    let remove: (() => void) | undefined;
    let exitArmedAt = 0;
    (async () => {
      const { App } = await import("@capacitor/app");
      const handle = await App.addListener("backButton", ({ canGoBack }) => {
        // 강제 업데이트 오버레이는 해제 불가 — 백버튼을 삼킨다.
        if (requiredRef.current === true) return;
        if (closeTopDismissable()) return;
        if (runTopBackHandler()) return;
        // 홈에서는 canGoBack(탭 전환으로 쌓인 히스토리)을 무시하고 종료로 간다.
        if (pathnameRef.current !== "/" && canGoBack) {
          window.history.back();
          return;
        }
        if (Date.now() - exitArmedAt < EXIT_CONFIRM_MS) {
          App.exitApp();
          return;
        }
        exitArmedAt = Date.now();
        toast("한 번 더 누르면 종료됩니다", { id: "exit-confirm", duration: EXIT_CONFIRM_MS });
      });
      remove = () => handle.remove();
    })();
    return () => remove?.();
  }, []);

  return null;
}
