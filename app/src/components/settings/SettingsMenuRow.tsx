"use client";

import { ChevronRightIcon, ExternalLinkIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type SettingsMenuRowVariant = "default" | "external" | "destructive";

interface SettingsMenuRowProps {
  label: string;
  onClick: () => void;
  variant?: SettingsMenuRowVariant;
  description?: string;
  /** 라벨 옆 unread 점(새 답변·새 공지 등). */
  dot?: boolean;
  /** chevron 왼쪽에 표시하는 현재값(예: 선택된 테마명). */
  value?: string;
}

/**
 * 설정 리스트 메뉴의 단일 행. 그룹 컨테이너
 * (`rounded-2xl bg-muted/60 overflow-hidden`) 안에 배치해 사용한다.
 * 같은 그룹의 행 사이에는 위쪽 구분선을 둔다(첫 행 제외).
 */
export function SettingsMenuRow({
  label,
  onClick,
  variant = "default",
  description,
  dot = false,
  value,
}: SettingsMenuRowProps) {
  const isDestructive = variant === "destructive";

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors",
        "border-t border-border/60 first:border-t-0",
        isDestructive
          ? "text-destructive hover:bg-destructive/10"
          : "text-foreground hover:bg-foreground/5",
      )}
    >
      <span className="min-w-0">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-[15px] font-medium">{label}</span>
          {dot ? (
            <span className="size-1.5 shrink-0 rounded-full bg-primary" aria-label="새 알림" />
          ) : null}
        </span>
        {description ? (
          <span className="mt-0.5 block truncate text-[12px] text-muted-foreground">
            {description}
          </span>
        ) : null}
      </span>

      {variant === "external" ? (
        <ExternalLinkIcon className="size-4 shrink-0 text-muted-foreground" />
      ) : isDestructive ? null : (
        <span className="flex shrink-0 items-center gap-1.5">
          {value ? (
            <span className="text-[14px] text-muted-foreground">{value}</span>
          ) : null}
          <ChevronRightIcon className="size-5 text-muted-foreground" />
        </span>
      )}
    </button>
  );
}
