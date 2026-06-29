"use client";

import { useEffect, useState } from "react";
import { getPlatform } from "@/lib/platform";
import { fetchAppConfig } from "@/lib/api/app-config";
import { useUpdateRequired } from "@/hooks/useUpdateRequired";
import { Button } from "@/components/base/Button";

/**
 * 네이티브 앱 실행 시 현재 버전이 BE 의 최소 지원 버전보다 낮으면
 * 해제 불가능한 전체 화면 오버레이를 띄워 스토어 업데이트를 강제한다.
 * - web 플랫폼은 체크하지 않는다(useUpdateRequired 가 false).
 * - 네트워크/조회 실패 시 강제하지 않는다(fail-open).
 * - ESC·외부 클릭은 plain overlay 라 동작하지 않고, Android 백버튼은 swallow 한다.
 */
export function ForceUpdateGate() {
  const required = useUpdateRequired();
  const [storeUrl, setStoreUrl] = useState("");

  // 강제 확정 시에만 스토어 URL 해결(fetchAppConfig 메모이즈 — 추가 네트워크 없음).
  useEffect(() => {
    if (required !== true) return;
    let cancelled = false;
    (async () => {
      try {
        const platform = getPlatform();
        if (platform === "web") return;
        const config = await fetchAppConfig();
        if (!cancelled) setStoreUrl(config.storeUrl[platform]);
      } catch {
        // fail-open: URL 조회 실패는 무시(버튼만 비활성).
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [required]);

  // 강제 상태 동안 Android 하드웨어 백버튼을 무력화(swallow)한다.
  useEffect(() => {
    if (required !== true) return;
    let remove: (() => void) | undefined;
    (async () => {
      const { App } = await import("@capacitor/app");
      const handle = await App.addListener("backButton", () => {});
      remove = () => handle.remove();
    })();
    return () => remove?.();
  }, [required]);

  if (required !== true) return null;

  const openStore = () => {
    if (!storeUrl) return;
    // _system: 인앱 브라우저가 아니라 스토어 앱/시스템 핸들러로 직접 연다.
    window.open(storeUrl, "_system");
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-6 bg-background px-8 text-center"
      style={{ paddingTop: "var(--safe-area-inset-top, env(safe-area-inset-top))", paddingBottom: "var(--safe-area-inset-bottom, env(safe-area-inset-bottom))" }}
    >
      <div className="flex flex-col gap-3">
        <h1 className="text-xl font-bold">업데이트가 필요합니다</h1>
        <p className="text-sm text-muted-foreground">
          원활한 사용을 위해 최신 버전으로 업데이트해 주세요.
          <br />
          업데이트 후 앱을 다시 실행할 수 있습니다.
        </p>
      </div>
      <Button size="xl" className="w-full max-w-xs" onClick={openStore}>
        지금 업데이트
      </Button>
    </div>
  );
}
