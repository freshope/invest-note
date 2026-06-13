"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { capturePageview } from "@/lib/analytics";

/** 라우트 변경마다 수동 $pageview. 최초 마운트 + 클라이언트 네비게이션 모두 포착. */
export function PageviewTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname) capturePageview(pathname);
  }, [pathname]);

  return null;
}
