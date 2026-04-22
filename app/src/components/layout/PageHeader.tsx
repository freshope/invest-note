import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * 두 가지 모드로 사용합니다.
 * - title/actions 모드: 텍스트 제목과 우측 액션 영역을 표준 레이아웃으로 렌더링
 * - children 모드: 홈 탭처럼 헤더 내부를 완전히 커스텀해야 할 때 사용.
 *   children이 있으면 title/actions는 무시됩니다 (두 모드는 배타적).
 */
type PageHeaderProps =
  | {
      /** 헤더 내부를 완전히 커스텀할 때 사용. title/actions와 함께 쓸 수 없습니다. */
      children: ReactNode;
      title?: never;
      actions?: never;
      sticky?: boolean;
      className?: string;
    }
  | {
      children?: never;
      /** 페이지 제목 텍스트 */
      title?: string;
      /** 헤더 오른쪽 액션 영역 (버튼, 토글 등) */
      actions?: ReactNode;
      sticky?: boolean;
      className?: string;
    };

export function PageHeader({
  title,
  actions,
  children,
  sticky = true,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        sticky && "sticky top-0 z-10",
        "bg-background px-5 pt-6 pb-3",
        className,
      )}
      style={{ paddingTop: "calc(1.5rem + env(safe-area-inset-top))" }}
    >
      {children ?? (
        <div className="flex items-center justify-between gap-3">
          <h1 className="min-w-0 truncate text-[20px] font-bold text-foreground leading-tight">
            {title}
          </h1>
          {actions && <div className="shrink-0">{actions}</div>}
        </div>
      )}
    </header>
  );
}
