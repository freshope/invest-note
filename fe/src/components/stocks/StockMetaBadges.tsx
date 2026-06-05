"use client";

import { useState, type SyntheticEvent } from "react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";

// 정보성 뱃지 — rise/fall(빨강·파랑)은 손익 전용이라 쓰지 않는다.
// 카드 배경(muted, 연회색)과 구분되도록 흰 배경 + 테두리로 띄운다.
const badgeClass =
  "text-[11px] font-bold px-1.5 py-0.5 rounded-md bg-background border border-border text-muted-foreground";

// 카드의 클릭/스와이프 레이어 안에 중첩되므로, 뱃지 탭이 카드 핸들러로 전파되지 않게 막는다.
function stop(e: SyntheticEvent) {
  e.stopPropagation();
}

const MARKET_DESC: Record<string, string> = {
  KOSPI: "유가증권시장(KOSPI)에 상장된 종목입니다.",
  KOSDAQ: "코스닥(KOSDAQ)에 상장된 종목입니다.",
  KONEX: "코넥스(KONEX)에 상장된 종목입니다.",
  ETF: "상장지수펀드(ETF)입니다.",
  ETN: "상장지수증권(ETN)입니다.",
};

interface SheetSection {
  label: string;
  title: string;
  description: string;
  /** 설명 아래 별도 줄로 표시할 공시 기준일. */
  asOf?: string | null;
}

/**
 * 종목 메타 뱃지 묶음 — 값이 있는 항목만 렌더한다. 부모의 flex 행에 직접 들어가도록 fragment 반환.
 * market 출처는 화면별로 다르다: 홈/종목상세=meta.market, 거래 화면=trade.exchange.
 *
 * 어떤 뱃지를 탭해도 바텀시트 하나가 열리고, 이 종목에 표시된 뱃지 전체의 설명을 한 페이지로 보여준다.
 * (모바일에서 Popover 는 위치가 불안정하고 뱃지별로 열고 닫아야 해서 바텀시트로 통일.)
 */
export function StockMetaBadges({
  market,
  rank,
  nps,
  npsAsOf,
}: {
  market?: string | null;
  rank?: number | null;
  nps?: "held" | "major" | null;
  npsAsOf?: string | null;
}) {
  const [open, setOpen] = useState(false);

  if (!market && rank == null && !nps) return null;

  // 종목명 옆에 표시되는 뱃지 — 값이 있는 것만.
  const badges: string[] = [];
  if (market) badges.push(market);
  if (rank != null) badges.push(`시총 ${rank}위`);
  if (nps) badges.push(nps === "major" ? "연금 5%+" : "연금보유");

  // 시트 섹션 — 연금은 어느 쪽이든 두 단계(보유/5%+) 설명을 모두 보여준다.
  const sections: SheetSection[] = [];
  if (market) {
    sections.push({
      label: market,
      title: "상장 시장",
      description: MARKET_DESC[market] ?? "종목이 상장된 시장 구분입니다.",
    });
  }
  if (rank != null) {
    sections.push({
      label: `시총 ${rank}위`,
      title: "시가총액 순위",
      description: "국내 주식(KOSPI·KOSDAQ 통합)의 시가총액 순위입니다. 매일 갱신됩니다.",
    });
  }
  if (nps) {
    sections.push(
      {
        label: "연금보유",
        title: "국민연금 보유",
        description: "국민연금이 보유 중인 종목입니다. (전체 보유 종목, 연 1회 공시)",
        asOf: npsAsOf,
      },
      {
        label: "연금 5%+",
        title: "국민연금 대량보유",
        description: "국민연금이 지분 5% 이상 보유 중인 종목입니다. (대량보유 보고, 분기 공시)",
        asOf: npsAsOf,
      },
    );
  }

  const openSheet = (e: SyntheticEvent) => {
    stop(e);
    setOpen(true);
  };

  return (
    <>
      {badges.map((label) => (
        <button
          key={label}
          type="button"
          className={`${badgeClass} cursor-pointer`}
          onClick={openSheet}
          onPointerDown={stop}
        >
          {label}
        </button>
      ))}
      {/* vaul 은 body 로 portal 되지만 React 합성 이벤트는 React 트리를 따라 카드
          onClick 까지 버블된다. 시트 전체의 click/pointerdown 전파를 이 경계에서
          차단한다. 이 차단이 Radix 의 외부 클릭 dismiss(document 레벨 리스너)까지
          막으므로, 오버레이 탭 닫기는 여기서 직접 처리한다. display:contents 라
          부모 flex 행에 박스를 추가하지 않는다. */}
      <span
        style={{ display: "contents" }}
        onPointerDown={stop}
        onClick={(e) => {
          stop(e);
          if (!(e.target as HTMLElement).closest('[data-slot="drawer-content"]')) setOpen(false);
        }}
      >
        <Drawer open={open} onOpenChange={setOpen}>
          <DrawerContent aria-describedby={undefined}>
            <DrawerHeader>
              <DrawerTitle>뱃지 안내</DrawerTitle>
            </DrawerHeader>
            <div className="space-y-4 px-5 pb-8">
              {sections.map((s) => (
                <div key={s.title}>
                  <div className="flex items-center gap-2">
                    <span className={badgeClass}>{s.label}</span>
                    <span className="text-[13px] font-bold text-foreground">{s.title}</span>
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                    {s.description}
                  </p>
                  {s.asOf && (
                    <p className="mt-0.5 text-[11px] text-muted-foreground/70">
                      기준일: {s.asOf}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </DrawerContent>
        </Drawer>
      </span>
    </>
  );
}
