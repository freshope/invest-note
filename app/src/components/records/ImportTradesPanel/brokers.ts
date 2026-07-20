export interface BrokerDownloadGuide {
  /** 거래내역서 형식 한 줄 설명 */
  description: string;
  /** 다운로드 절차 단계 (모바일 앱 기준) */
  steps: string[];
  /** 증권사 도움말 페이지 URL (선택) */
  helpUrl?: string;
}

export interface BrokerOption {
  key: "samsung_xlsx" | "toss_pdf" | "shinhan_pdf" | "mirae_pdf" | "koreainvest_xls";
  label: string;
  accept: string;
  downloadGuide: BrokerDownloadGuide;
}

// description(문서명)·accept(형식)는 파서 docstring·sample/ 실제 export 파일명과 대조 완료.
// 삼성 steps = PC 웹(samsungpop.com) 엑셀 다운로드로 정정(모바일 앱엔 xlsx 내보내기 없음, 실사용 확인 2026-07-02).
// 토스 steps = 공식 FAQ(support.toss.im/faq/3331) 앱 경로로 정정(2026-07-02).
// TODO 미검수: 신한·미래에셋·한국투자 steps(웹/앱 메뉴 경로) — 계정 없어 캡처 대기.
// 앱·웹 화면 메뉴 라벨/단계가 바뀌면 여기를 갱신한다.
export const BROKER_OPTIONS: readonly BrokerOption[] = [
  {
    key: "samsung_xlsx",
    label: "삼성증권",
    accept: ".xlsx,.xls",
    downloadGuide: {
      description: "거래내역서 (xlsx)",
      steps: [
        "PC 웹브라우저에서 삼성증권 홈페이지(samsungpop.com) 로그인 (모바일 mPOP 앱에는 엑셀 내보내기가 없음)",
        "거래내역 조회 화면에서 계좌·조회기간·조회구분 선택 후 [조회]",
        "[엑셀파일다운로드] 버튼으로 .xlsx 저장 (기간 최근 1년 이내 권장)",
        "저장한 xlsx 를 휴대폰으로 옮긴 뒤 이 화면에 업로드",
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
        "토스 앱 → 토스증권 홈 → 우측 상단 회색 삼단바(≡)",
        "설정 → 계좌관리 → '증명서 발급하기'",
        "증명서 종류에서 '거래 내역서' 선택 후 기간 지정",
        "PDF 로 발급한 뒤 이 화면에 업로드",
      ],
      helpUrl: "https://support.toss.im/faq/3331",
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
      description: "거래내역증명서 (PDF)",
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
  {
    key: "koreainvest_xls",
    label: "한국투자증권",
    accept: ".xls",
    downloadGuide: {
      description: "거래내역서 (xls)",
      steps: [
        "한국투자증권 홈페이지(securities.koreainvestment.com) 로그인 (PC 웹)",
        "거래내역 조회 화면에서 계좌·조회기간·업무구분(매매) 선택 후 [조회]",
        "[엑셀다운로드] 버튼으로 .xls 저장",
        "저장한 xls 를 휴대폰으로 옮긴 뒤 이 화면에 업로드",
      ],
      helpUrl: "https://securities.koreainvestment.com",
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

// 파일명 확장자가 accept(".pdf" 또는 ".xlsx,.xls") 중 하나와 일치하는지.
// accept 는 native 피커의 힌트일 뿐 드래그-드롭/일부 모바일 피커에서 강제되지 않으므로
// 선택 직후 한 번 더 검증해 잘못된 형식이 BE 분석까지 가는 것을 막는다.
export function isAcceptedExtension(filename: string, accept: string): boolean {
  const exts = accept
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  if (exts.length === 0) return true;
  const lower = filename.toLowerCase();
  return exts.some((ext) => lower.endsWith(ext));
}
