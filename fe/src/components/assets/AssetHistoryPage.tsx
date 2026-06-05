"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { AssetHistoryView } from "./AssetHistoryView";
import { useHideBottomNav } from "@/components/providers/BottomNavProvider";

/**
 * /assets 라우트(홈 헤더 진입, 계좌 자산 변화). 종목상세 진입은 DetailPanelProvider 패널로 처리한다.
 * 패널과 동일하게 풀스크린(fixed) 컬럼 + 하단 네비 숨김(언마운트 시 자동 복구).
 */
export function AssetHistoryPage() {
  const params = useSearchParams();
  const router = useRouter();
  useHideBottomNav(true);

  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-background">
      <AssetHistoryView
        ticker={params.get("ticker")}
        country={params.get("country")}
        name={params.get("name")}
        onBack={() => router.back()}
      />
    </div>
  );
}
