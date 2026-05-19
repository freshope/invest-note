"use client";

import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import LibPullToRefresh from "react-simple-pull-to-refresh";

interface PullToRefreshProps {
  onRefresh: () => Promise<unknown>;
  children: ReactNode;
  isPullable?: boolean;
}

function Indicator({ spinning }: { spinning: boolean }) {
  return (
    <div className="flex h-12 items-center justify-center text-muted-foreground">
      <Loader2
        className={`size-5 ${spinning ? "animate-spin" : "opacity-60"}`}
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
  return (
    <LibPullToRefresh
      onRefresh={async () => {
        await onRefresh();
      }}
      isPullable={isPullable}
      pullingContent={<Indicator spinning={false} />}
      refreshingContent={<Indicator spinning />}
      pullDownThreshold={64}
      maxPullDownDistance={96}
      resistance={2.5}
    >
      <div className="h-full w-full">{children}</div>
    </LibPullToRefresh>
  );
}
