"use client";

import { Suspense } from "react";
import { AssetHistoryPage } from "@/components/assets/AssetHistoryPage";

// 정적 export 환경에서 useSearchParams 는 Suspense 경계가 필요하다(login/page 패턴).
export default function AssetsPage() {
  return (
    <Suspense fallback={null}>
      <AssetHistoryPage />
    </Suspense>
  );
}
