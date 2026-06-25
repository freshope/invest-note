export interface BrokerDownloadGuide {
  /** 거래내역서 형식 한 줄 설명 */
  description: string;
  /** 다운로드 절차 단계 (모바일 앱 기준) */
  steps: string[];
  /** 증권사 도움말 페이지 URL (선택) */
  helpUrl?: string;
}

export interface BrokerOption {
  key: "samsung_xlsx" | "toss_pdf" | "shinhan_pdf" | "mirae_pdf";
  label: string;
  accept: string;
  downloadGuide: BrokerDownloadGuide;
}

// TODO: 다운로드 가이드는 AI 1차 초안 — 실제 증권사 앱과 대조 후 검수 필요.
// 앱 화면 메뉴 라벨/단계가 바뀌면 여기를 갱신한다.
export const BROKER_OPTIONS: readonly BrokerOption[] = [
  {
    key: "samsung_xlsx",
    label: "삼성증권",
    accept: ".xlsx,.xls",
    downloadGuide: {
      description: "기간별 매매내역서 (xlsx)",
      steps: [
        "삼성증권 mPOP 앱 로그인",
        "메뉴 → 거래내역 → 기간별 매매내역",
        "조회 기간 선택 (최근 1년 이내 권장)",
        "엑셀(.xlsx) 다운로드 후 이 화면에 업로드",
      ],
      helpUrl: "https://www.samsungpop.com",
    },
  },
  {
    key: "toss_pdf",
    label: "토스증권",
    accept: ".pdf",
    downloadGuide: {
      description: "거래내역서 (PDF)",
      steps: [
        "토스 앱 → 주식 탭",
        "오른쪽 상단 메뉴 → 거래내역 확인",
        "기간 선택 후 PDF로 내보내기",
        "저장된 PDF 를 이 화면에 업로드",
      ],
      helpUrl: "https://tossinvest.com",
    },
  },
  {
    key: "shinhan_pdf",
    label: "신한투자증권",
    accept: ".pdf",
    downloadGuide: {
      description: "거래내역서 (PDF)",
      steps: [
        "신한 SOL증권 앱 로그인",
        "메뉴 → 거래내역 → 기간별 거래내역",
        "조회 기간 선택 후 PDF로 내보내기",
        "저장된 PDF 를 이 화면에 업로드",
      ],
      helpUrl: "https://www.shinhansec.com",
    },
  },
  {
    key: "mirae_pdf",
    label: "미래에셋증권",
    accept: ".pdf",
    downloadGuide: {
      description: "거래내역서 (PDF)",
      steps: [
        "미래에셋 m.Stock 앱 로그인",
        "메뉴 → 거래내역 → 기간별 거래내역",
        "조회 기간 선택 후 PDF로 출력",
        "출력 시 '암호 없는 버전으로 출력' 선택 (암호가 걸린 PDF 는 업로드 불가)",
        "저장된 PDF 를 이 화면에 업로드",
      ],
      helpUrl: "https://securities.miraeasset.com",
    },
  },
] as const;

export type BrokerKey = BrokerOption["key"];

export function findBrokerKeyByAccountBroker(
  broker: string | null | undefined
): BrokerKey | null {
  if (!broker) return null;
  const matched = BROKER_OPTIONS.find((b) => b.label === broker);
  return matched ? matched.key : null;
}
