"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/base/Button";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { capture } from "@/lib/analytics";
import { requestRegisterChooserOpen } from "@/lib/register-chooser-deeplink";

interface EmptyStateProps {
  variant: "no-accounts" | "no-trades";
}

// 인라인 계좌등록(거래폼 내 "새 계좌 추가") 도입으로 계좌는 거래 등록 흐름에서 자동 생성된다.
// 신규 유저에게 "계좌"라는 미지의 개념을 노출하지 않고, 거래 기록으로 얻는 가치를 제시해
// 첫 활성화를 유도한다(계좌 언급 제거).
const emptyStateContent = {
  "no-accounts": {
    title: "첫 거래를 기록해보세요",
    description: "거래를 기록하면 자산과 손익이 자동으로 정리돼요",
    action: "거래 기록하기",
  },
  "no-trades": {
    title: "아직 거래 기록이 없어요",
    description: "거래를 기록하면 자산과 손익이 자동으로 정리돼요",
    action: "거래 기록하기",
  },
} satisfies Record<
  EmptyStateProps["variant"],
  { title: string; description: string; action: string }
>;

export function EmptyState({ variant }: EmptyStateProps) {
  const router = useRouter();
  const content = emptyStateContent[variant];

  const handleClick = () => {
    capture("empty_state_cta_clicked", { variant });
    // /records 로 이동 후 등록 chooser(매수/매도/거래내역서 업로드)를 자동으로 연다.
    // 거래 탭 FAB(+) 와 동일한 진입점으로 통일 (import 딥링크와 동일 패턴).
    requestRegisterChooserOpen();
    router.push("/records");
  };

  return (
    <div className="px-5">
      <EmptyCard
        title={content.title}
        description={content.description}
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={handleClick}
            className="rounded-xl font-semibold"
          >
            {content.action}
          </Button>
        }
      />
    </div>
  );
}
