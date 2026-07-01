"use client";

import { useCallback, useRef } from "react";
import { toast } from "sonner";
import { tradesApi, ApiError } from "@/lib/api-client";
import type { StockPayload } from "@/components/panels/DetailPanelProvider";
import type { Position } from "@/lib/portfolio";

/**
 * 보유 종목(Position)을 눌러 종목 상세 패널을 여는 공통 동작.
 * 대상 종목의 거래내역을 먼저 불러온 뒤 openStock 한다(전환 시 빈 플래시 방지).
 * 홈 보유목록(HoldingsList)과 헤더 종목 전환(StockSwitchSheet)이 공유한다.
 *
 * openStock 은 호출처에서 주입한다 — useDetailPanel 을 직접 import 하면
 * DetailPanelProvider 와 순환 import 가 되므로 인자로 받는다(StockPayload 는 type-only import).
 */
export function useOpenStock(
  openStock: (payload: StockPayload, source?: string) => void,
  source?: string,
): (position: Position) => Promise<void> {
  // 진행 중 여부는 렌더 트리거가 필요 없는 가드 플래그라 ref 로 보관해 콜백을 stable 하게 유지한다.
  const fetchingRef = useRef(false);

  return useCallback(
    async (pos: Position) => {
      if (fetchingRef.current) return;
      fetchingRef.current = true;
      try {
        const { trades, accounts } = await tradesApi.list({
          ticker: pos.ticker,
          country: pos.country,
        });
        openStock({
          assetName: pos.assetName,
          nameKo: pos.nameKo,
          ticker: pos.ticker,
          country: pos.country,
          allTrades: trades,
          accounts,
        }, source);
      } catch (err) {
        const toastId = "holdings-fetch-error";
        if (err instanceof ApiError) {
          const msg = err.status === 401
            ? "다시 로그인해 주세요"
            : "보유 종목을 불러오지 못했어요 (서버 오류)";
          toast.error(msg, { id: toastId });
        } else {
          toast.error("네트워크 연결을 확인해 주세요", { id: toastId });
        }
      } finally {
        fetchingRef.current = false;
      }
    },
    [openStock, source],
  );
}
