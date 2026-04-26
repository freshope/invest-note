import Link from "next/link";
import { buttonVariants } from "@/components/base/Button";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  variant: "no-accounts" | "no-trades";
}

const emptyStateContent = {
  "no-accounts": {
    title: "아직 계좌가 없어요",
    description: "계좌를 추가하면 보유 종목과 손익을 확인할 수 있어요",
    href: "/settings",
    action: "계좌 추가하기",
  },
  "no-trades": {
    title: "아직 거래 기록이 없어요",
    description: "첫 번째 거래를 기록하면 포트폴리오가 표시돼요",
    href: "/records",
    action: "거래 기록하기",
  },
} satisfies Record<
  EmptyStateProps["variant"],
  { title: string; description: string; href: string; action: string }
>;

export function EmptyState({ variant }: EmptyStateProps) {
  const content = emptyStateContent[variant];

  return (
    <div className="px-5">
      <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4">
        <div className="space-y-1">
          <p className="text-[15px] font-semibold text-foreground">{content.title}</p>
          <p className="text-[13px] text-muted-foreground">
            {content.description}
          </p>
        </div>
        <Link
          href={content.href}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "rounded-xl font-semibold")}
        >
          {content.action}
        </Link>
      </div>
    </div>
  );
}
