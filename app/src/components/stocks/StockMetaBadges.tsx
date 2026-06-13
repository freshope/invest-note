"use client";

import { useState, type ReactNode, type SyntheticEvent } from "react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";
import { CountryBadge } from "@/components/records/trade-display";

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
  NASDAQ: "나스닥(NASDAQ)에 상장된 미국 종목입니다.",
  NYSE: "뉴욕증권거래소(NYSE)에 상장된 미국 종목입니다.",
  "NYSE ARCA": "NYSE Arca 거래소에 상장된 미국 종목입니다(주로 ETF).",
  "NYSE MKT": "NYSE American(구 AMEX) 거래소에 상장된 미국 종목입니다.",
  "Cboe BZX": "Cboe BZX 거래소에 상장된 미국 종목입니다(주로 ETF).",
};

const COUNTRY_DESC: Record<string, string> = {
  KR: "국내(KOSPI·KOSDAQ) 시장에 상장된 종목입니다.",
  US: "미국 시장(NASDAQ·NYSE 등)에 상장된 해외 종목입니다.",
};

// US 지수 편입 라벨. 미지의 값은 폴백(?? usIndex)으로 raw 표시 — NASDAQ100 등도 안 깨짐.
const US_INDEX_LABEL: Record<string, string> = { SP500: "S&P 500" };

interface SheetSection {
  /** 시트 헤더에 표시할 뱃지 미니어처(목록의 실제 뱃지와 동일 모양). */
  badge: ReactNode;
  title: string;
  description: string;
  /** 설명 아래 별도 줄로 표시할 공시 기준일. */
  asOf?: string | null;
}

/**
 * 종목 식별 태그 묶음 — 국가 + 상장시장 + 시가총액 순위 + 국민연금 보유 + 인덱스 편입. 값이 있는
 * 것만 렌더하고, 부모의 flex 행에 직접 들어가도록 fragment 를 반환한다. 종목 카드/상세/거래 화면이
 * 모두 이 한 컴포넌트를 써서 표시 묶음과 클릭 설명을 일관되게 유지한다.
 *
 * - `countryCode`: 국내/해외 구분 뱃지(색상은 CountryBadge).
 * - `market`: 상장 시장/거래소. **거래에 기록된 exchange(KOSPI/KOSDAQ/NASDAQ…) 를 우선**으로
 *   넘기고 meta.market 은 폴백 — exchange 없는 거래는 meta.market(KR/US 모두 제공)으로 표시된다.
 * - `rank`/`nps`: KR 전용 메타(시총순위·국민연금). US 는 비어 있는 게 정상.
 * - `usIndex`: US 전용 메타(인덱스 편입, 예 'SP500'). KR 은 비어 있는 게 정상.
 *
 * 어떤 뱃지를 탭해도 바텀시트 하나가 열리고, 이 종목에 표시된 뱃지 전체의 설명을 한 페이지로 보여준다.
 * (모바일에서 Popover 는 위치가 불안정하고 뱃지별로 열고 닫아야 해서 바텀시트로 통일.)
 */
export function StockMetaBadges({
  countryCode,
  market,
  rank,
  nps,
  npsAsOf,
  usIndex,
}: {
  countryCode?: string | null;
  market?: string | null;
  rank?: number | null;
  nps?: "held" | "major" | null;
  npsAsOf?: string | null;
  usIndex?: string | null;
}) {
  const [open, setOpen] = useState(false);

  if (!countryCode && !market && rank == null && !nps && !usIndex) return null;

  const usIndexLabel = usIndex ? US_INDEX_LABEL[usIndex] ?? usIndex : null;

  const openSheet = (e: SyntheticEvent) => {
    stop(e);
    setOpen(true);
  };

  // 시트 섹션 — 표시된 뱃지와 1:1. 연금은 어느 쪽이든 두 단계(보유/5%+) 설명을 모두 보여준다.
  const sections: SheetSection[] = [];
  if (countryCode) {
    sections.push({
      badge: <CountryBadge countryCode={countryCode} />,
      title: "상장 국가",
      description: COUNTRY_DESC[countryCode] ?? "해당 종목의 상장 국가 구분입니다.",
    });
  }
  if (market) {
    sections.push({
      badge: <span className={badgeClass}>{market}</span>,
      title: "상장 시장",
      description: MARKET_DESC[market] ?? "종목이 상장된 시장 구분입니다.",
    });
  }
  if (rank != null) {
    sections.push({
      badge: <span className={badgeClass}>{`시총 ${rank}위`}</span>,
      title: "시가총액 순위",
      description: "국내 주식(KOSPI·KOSDAQ 통합)의 시가총액 순위입니다. 매일 갱신됩니다.",
    });
  }
  if (usIndexLabel) {
    sections.push({
      badge: <span className={badgeClass}>{usIndexLabel}</span>,
      title: "지수 편입",
      description: `${usIndexLabel} 지수에 편입된 미국 종목입니다.`,
    });
  }
  if (nps) {
    sections.push(
      {
        badge: <span className={badgeClass}>연금보유</span>,
        title: "국민연금 보유",
        description: "국민연금이 보유 중인 종목입니다. (전체 보유 종목, 연 1회 공시)",
        asOf: npsAsOf,
      },
      {
        badge: <span className={badgeClass}>연금 5%+</span>,
        title: "국민연금 대량보유",
        description: "국민연금이 지분 5% 이상 보유 중인 종목입니다. (대량보유 보고, 분기 공시)",
        asOf: npsAsOf,
      },
    );
  }

  return (
    <>
      {countryCode && (
        <button type="button" className="cursor-pointer" onClick={openSheet} onPointerDown={stop}>
          <CountryBadge countryCode={countryCode} />
        </button>
      )}
      {market && (
        <button
          type="button"
          className={`${badgeClass} cursor-pointer`}
          onClick={openSheet}
          onPointerDown={stop}
        >
          {market}
        </button>
      )}
      {rank != null && (
        <button
          type="button"
          className={`${badgeClass} cursor-pointer`}
          onClick={openSheet}
          onPointerDown={stop}
        >
          {`시총 ${rank}위`}
        </button>
      )}
      {usIndexLabel && (
        <button
          type="button"
          className={`${badgeClass} cursor-pointer`}
          onClick={openSheet}
          onPointerDown={stop}
        >
          {usIndexLabel}
        </button>
      )}
      {nps && (
        <button
          type="button"
          className={`${badgeClass} cursor-pointer`}
          onClick={openSheet}
          onPointerDown={stop}
        >
          {nps === "major" ? "연금 5%+" : "연금보유"}
        </button>
      )}
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
                    {s.badge}
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
