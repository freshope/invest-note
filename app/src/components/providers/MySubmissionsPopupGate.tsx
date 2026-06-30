"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";
import { Button } from "@/components/base/Button";
import { boardApi, type MyPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useAuth } from "@/components/providers/AuthProvider";
import { requestImportOpen } from "@/lib/import-deeplink";
import { useUpdateRequired } from "@/hooks/useUpdateRequired";

/**
 * 앱 진입 시 미확인 resolved 거래내역서 제보 1건을 바텀시트로 안내한다(정확히 1회).
 * - 인증된 사용자만 조회(토큰 없으면 비활성).
 * - 강제 업데이트가 필요한 상태면 팝업을 띄우지 않고 ack 도 하지 않는다(one-shot 보존).
 *   ForceUpdateGate 와 동일 판정(useUpdateRequired) 공유 — 둘 다 fetchAppConfig 메모이즈 사용.
 */
export function MySubmissionsPopupGate() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  // 강제 업데이트 판정: undefined=미정(대기), false=비강제, true=강제(팝업 금지).
  const updateRequired = useUpdateRequired();

  // 강제 업데이트가 아닐 때만(=false 확정) + 인증 사용자만 조회.
  const enabled = !!user && updateRequired === false;

  const { data } = useQuery({
    queryKey: queryKeys.myPosts,
    queryFn: () => boardApi.myPosts(),
    enabled,
    // 진입 1회용 — 포커스 재조회 끄고 staleTime 길게(세션당 사실상 1회).
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  // 미확인 resolved 거래내역서 제보 중 1건(글 목록 created_at desc → 첫 매칭).
  // 미확인 판정은 서버 플래그(popup_acked) — 기기 무관 1회 dedup.
  // `=== false` 명시 비교: BE-lag(OTA 선행)로 필드 부재 시 undefined → 미노출(안전). `!popup_acked`
  // 면 undefined 가 truthy 처리돼 ack 불가 구간에 매 진입마다 팝업이 떠버린다.
  const target = useMemo<MyPost | null>(() => {
    if (!data) return null;
    return (
      data.items.find(
        (p) =>
          p.status === "resolved" &&
          p.board_type === "broker_statement" &&
          p.popup_acked === false,
      ) ?? null
    );
  }, [data]);

  const [open, setOpen] = useState(false);
  // 한 번 ack 한 id 는 다시 노출하지 않는다(같은 세션 재오픈 방지).
  const [acked, setAcked] = useState(false);

  // target 이 나타나면(미ack) 자동 오픈. effect 동기 setState 대신 렌더 중 조정(React 공식 패턴).
  // !open 가드로 1회만 set → 무한 렌더 없음. ack 후엔 acked=true 라 재오픈 안 됨.
  if (target && !acked && !open) {
    setOpen(true);
  }

  if (!target) return null;

  const ack = () => {
    // 서버 popup_acked 처리 → my-posts invalidate 로 기기 무관 dedup. 로컬 acked 는 같은 세션 재오픈 방지.
    void boardApi
      .ackPopup(target.id)
      .then(() =>
        queryClient.invalidateQueries({ queryKey: queryKeys.myPosts }),
      )
      .catch(() => {});
    setAcked(true);
    setOpen(false);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) ack();
    else setOpen(true);
  };

  const goImport = () => {
    ack();
    requestImportOpen();
    router.push("/records");
  };

  const broker = target.metadata.broker ?? "제보하신 증권사";

  return (
    <Drawer open={open} onOpenChange={handleOpenChange}>
      <DrawerContent aria-describedby={undefined}>
        <DrawerHeader>
          <DrawerTitle>🎉 일괄등록이 가능해졌어요</DrawerTitle>
        </DrawerHeader>
        <div className="space-y-5 px-5 pb-8">
          <p className="text-[14px] leading-relaxed text-muted-foreground">
            제보해주신 <span className="font-semibold text-foreground">{broker}</span>{" "}
            거래내역서를 이제 일괄등록으로 한 번에 불러올 수 있어요.
          </p>
          <Button size="xl" className="w-full" onClick={goImport}>
            지금 가져오기
          </Button>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
