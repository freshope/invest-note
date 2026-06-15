"use client";

import { useState } from "react";
import { InfoIcon } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";
import { cn } from "@/lib/utils";

export interface InfoHintItem {
  /** 항목 제목(선택). 없으면 설명만 한 줄로 보여준다. */
  title?: string;
  description: string;
}

/**
 * 중립 설명문구를 인라인으로 깔지 않고, 값/날짜 옆 Info 아이콘 뒤 바텀시트로 안내한다.
 * `StockMetaBadges` 의 Drawer 패턴을 일반화한 공유 컴포넌트 — 단, 클릭 가능한 카드 안에
 * 중첩되지 않는 단독 트리거라 거기서 쓰는 stop()/display:contents 복잡도는 두지 않는다.
 *
 * 경고/에러는 이 시트에 넣지 않는다(가시성 유지를 위해 호출부에서 인라인으로 띄운다).
 */
export function InfoHintSheet({
  items,
  title = "안내",
  ariaLabel = "안내 보기",
  className,
}: {
  items: InfoHintItem[];
  title?: string;
  ariaLabel?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  if (items.length === 0) return null;

  return (
    <>
      <button
        type="button"
        aria-label={ariaLabel}
        onClick={(e) => {
          // 시트가 열리며 <main>에 aria-hidden이 씌워지기 전에 트리거 포커스를 해제한다.
          // (포커스된 요소가 aria-hidden 조상 아래 남으면 접근성 경고 발생)
          e.currentTarget.blur();
          setOpen(true);
        }}
        className={cn(
          "shrink-0 text-muted-foreground/70 transition-colors hover:text-muted-foreground",
          className,
        )}
      >
        <InfoIcon className="size-4" />
      </button>
      <Drawer open={open} onOpenChange={setOpen}>
        <DrawerContent aria-describedby={undefined}>
          <DrawerHeader>
            <DrawerTitle>{title}</DrawerTitle>
          </DrawerHeader>
          <div className="space-y-4 px-5 pb-8">
            {items.map((item, i) => (
              <div key={i}>
                {item.title && (
                  <p className="text-[13px] font-bold text-foreground">{item.title}</p>
                )}
                <p
                  className={cn(
                    "text-[12px] leading-relaxed text-muted-foreground",
                    item.title && "mt-1",
                  )}
                >
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}
