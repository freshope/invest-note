"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import LibPullToRefresh from "react-simple-pull-to-refresh";
import { hapticImpact } from "@/lib/haptics";

interface PullToRefreshProps {
  onRefresh: () => Promise<unknown>;
  children: ReactNode;
  isPullable?: boolean;
}

function Indicator({ spinning }: { spinning: boolean }) {
  return (
    <div
      className="flex items-start justify-center text-muted-foreground"
      style={{ paddingTop: "calc(env(safe-area-inset-top) + 0.5rem)" }}
    >
      <Loader2
        className={`size-5 ${spinning ? "animate-spin" : "opacity-70"}`}
        aria-hidden
      />
    </div>
  );
}

export function PullToRefresh({
  onRefresh,
  children,
  isPullable = true,
}: PullToRefreshProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = wrapperRef.current;
    if (!root) return;
    const ptr = root.querySelector<HTMLElement>(".ptr");
    if (!ptr) return;

    let lastBreached = false;
    // 스레숄드를 처음 넘는 순간 한 번만 햅틱 — iOS 네이티브 pull-to-refresh 와 동일한 UX.
    const observer = new MutationObserver(() => {
      const breached = ptr.classList.contains(
        "ptr--pull-down-treshold-breached",
      );
      if (breached && !lastBreached) {
        void hapticImpact("light");
      }
      lastBreached = breached;
    });
    observer.observe(ptr, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={wrapperRef}>
      <LibPullToRefresh
        onRefresh={async () => {
          await onRefresh();
        }}
        isPullable={isPullable}
        pullingContent={<Indicator spinning={false} />}
        refreshingContent={<Indicator spinning />}
        pullDownThreshold={80}
        maxPullDownDistance={110}
        resistance={2.5}
      >
        <div className="h-full w-full">{children}</div>
      </LibPullToRefresh>
    </div>
  );
}
