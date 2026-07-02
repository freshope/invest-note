"use client";

import { FileCheckIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { SEMANTIC_COLORS } from "@/lib/constants/semantic-colors";
import type { Trade } from "@/types/database";

type ImportSourceBadgeSize = "sm" | "md";

const SIZE_CLASSES: Record<ImportSourceBadgeSize, string> = {
  sm: "text-[11px] px-1.5 py-0.5 gap-0.5",
  md: "text-[12px] px-2 py-0.5 gap-1",
};

const ICON_SIZE: Record<ImportSourceBadgeSize, string> = {
  sm: "size-3",
  md: "size-3.5",
};

interface ImportSourceBadgeProps {
  origin: Trade["origin"];
  size?: ImportSourceBadgeSize;
  className?: string;
}

// 거래내역서(증권사 일괄등록)에서 가져온 거래 표식. 그린 틴트(채워진)로 중립 정보 뱃지
// (MarketTypeBadge/StockMetaBadges: 흰 배경+테두리)와 구별한다. 손익(rise/fall, 빨강/파랑)은
// 금액 전용이라 쓰지 않는다 — 그린은 import 플로우(PreviewStep/ResultStep) 성공색과 일관. IMPORT 일 때만 렌더.
export function ImportSourceBadge({ origin, size = "md", className }: ImportSourceBadgeProps) {
  if (origin !== "IMPORT") return null;
  return (
    <span
      className={cn(
        "inline-flex items-center font-bold rounded-md border shrink-0",
        SEMANTIC_COLORS.success.bgSoft,
        SEMANTIC_COLORS.success.borderSoft,
        SEMANTIC_COLORS.success.text,
        SIZE_CLASSES[size],
        className,
      )}
    >
      <FileCheckIcon className={ICON_SIZE[size]} strokeWidth={2.25} />
      거래내역서
    </span>
  );
}
