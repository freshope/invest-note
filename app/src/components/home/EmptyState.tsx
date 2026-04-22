import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  variant: "no-accounts" | "no-trades";
}

export function EmptyState({ variant }: EmptyStateProps) {
  if (variant === "no-accounts") {
    return (
      <div className="px-5">
        <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4">
          <div className="space-y-1">
            <p className="text-[15px] font-semibold text-foreground">아직 계좌가 없어요</p>
            <p className="text-[13px] text-muted-foreground">
              계좌를 추가하면 보유 종목과 손익을 확인할 수 있어요
            </p>
          </div>
          <Link
            href="/settings"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "rounded-xl font-semibold")}
          >
            계좌 추가하기
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="px-5">
      <div className="rounded-2xl bg-muted/60 p-8 text-center space-y-4">
        <div className="space-y-1">
          <p className="text-[15px] font-semibold text-foreground">아직 거래 기록이 없어요</p>
          <p className="text-[13px] text-muted-foreground">
            첫 번째 거래를 기록하면 포트폴리오가 표시돼요
          </p>
        </div>
        <Link
          href="/records"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "rounded-xl font-semibold")}
        >
          거래 기록하기
        </Link>
      </div>
    </div>
  );
}
