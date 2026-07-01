"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/base/Button";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { capture } from "@/lib/analytics";
import { requestTradeFormOpen } from "@/lib/trade-form-deeplink";

interface EmptyStateProps {
  variant: "no-accounts" | "no-trades";
}

// 인라인 계좌등록(거래폼 내 "새 계좌 추가") 도입으로 no-accounts 도 계좌 사전등록 없이
// 거래 등록 흐름으로 바로 유도한다(더 이상 /settings 로 보내지 않음). 문구만 맥락 유지.
const emptyStateContent = {
  "no-accounts": {
    title: "아직 계좌가 없어요",
    description: "첫 거래를 기록하면 계좌도 함께 만들 수 있어요",
    action: "거래 기록하기",
  },
  "no-trades": {
    title: "아직 거래 기록이 없어요",
    description: "첫 번째 거래를 기록하면 포트폴리오가 표시돼요",
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
    // /records 로 이동 후 거래 등록 폼(매수)을 자동으로 연다(import 딥링크와 동일 패턴).
    requestTradeFormOpen();
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
