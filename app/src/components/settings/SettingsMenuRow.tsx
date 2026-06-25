"use client";

import { ChevronRightIcon, ExternalLinkIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type SettingsMenuRowVariant = "default" | "external" | "destructive";

interface SettingsMenuRowProps {
  label: string;
  onClick: () => void;
  variant?: SettingsMenuRowVariant;
  description?: string;
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
        <span className="block truncate text-[15px] font-medium">{label}</span>
        {description ? (
          <span className="mt-0.5 block truncate text-[12px] text-muted-foreground">
            {description}
          </span>
        ) : null}
      </span>

      {variant === "external" ? (
        <ExternalLinkIcon className="size-4 shrink-0 text-muted-foreground" />
      ) : isDestructive ? null : (
        <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
      )}
    </button>
  );
}
