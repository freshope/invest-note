"use client";

import { ArrowDownIcon, ArrowUpIcon, UploadIcon } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";
import { PNL_COLORS } from "@/lib/constants/colors";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectBuy: () => void;
  onSelectSell: () => void;
  onSelectImport: () => void;
}

/**
 * 등록 진입점 통합 chooser. FAB(+) 를 눌렀을 때 [매수 / 매도 / 거래내역서 업로드] 중
 * 하나를 고르게 하는 바텀시트. 매수·매도를 동등 primary(둘 다 solid 채움)로 제시해
 * 첫 활성화 동선을 대칭으로 유도하고, 거래내역서 업로드는 중립 카드로 둔다.
 * 색상 규칙: 매수=rise(빨강) / 매도=fall(파랑).
 */
export function RegisterChooser({
  open,
  onOpenChange,
  onSelectBuy,
  onSelectSell,
  onSelectImport,
}: Props) {
  const choose = (fn: () => void) => {
    onOpenChange(false);
    fn();
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent aria-describedby={undefined}>
        <DrawerHeader>
          <DrawerTitle>어떤 거래를 기록할까요?</DrawerTitle>
        </DrawerHeader>
        <div className="space-y-2.5 px-5 pb-8">
          {/* 매수 — solid 채움(rise) */}
          <button
            type="button"
            onClick={() => choose(onSelectBuy)}
            className={cn(
              "flex w-full items-center gap-3 rounded-2xl px-4 py-4 text-left text-white active:scale-[0.99] transition-transform",
              PNL_COLORS.rise.bg,
            )}
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/20">
              <ArrowUpIcon className="h-6 w-6" strokeWidth={2.5} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[16px] font-bold">매수 기록</span>
              <span className="block text-[13px] text-white/80">종목을 새로 담았어요</span>
            </span>
          </button>

          {/* 매도 — solid 채움(fall), 매수와 대칭 */}
          <button
            type="button"
            onClick={() => choose(onSelectSell)}
            className={cn(
              "flex w-full items-center gap-3 rounded-2xl px-4 py-4 text-left text-white active:scale-[0.99] transition-transform",
              PNL_COLORS.fall.bg,
            )}
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/20">
              <ArrowDownIcon className="h-6 w-6" strokeWidth={2.5} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[16px] font-bold">매도 기록</span>
              <span className="block text-[13px] text-white/80">보유 종목을 팔았어요</span>
            </span>
          </button>

          {/* 거래내역서 업로드 */}
          <button
            type="button"
            onClick={() => choose(onSelectImport)}
            className="flex w-full items-center gap-3 rounded-2xl border bg-card px-4 py-4 text-left active:scale-[0.99] transition-transform"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <UploadIcon className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[16px] font-bold text-foreground">거래내역서 업로드</span>
              <span className="block text-[13px] text-muted-foreground">증권사 파일로 한 번에 등록</span>
            </span>
          </button>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
