/**
 * semantic(성공/경고/정보/위험) 색상 클래스 토큰.
 *
 * PNL_COLORS(pnl-colors.ts) 패턴을 복제한다. Tailwind JIT가 정적 string에서
 * 추출하므로 동적 보간(`text-[var(--${key})]`)은 금지 — 정적 string으로 나열.
 * 색 자체의 hex 값은 globals.css의 `:root`/`.dark`에서 `--success/--warning/--info/--danger`로 정의.
 * soft 배경은 알파(`bg-[var(--success)]/10`)로 표현해 라이트/다크 자동 대응.
 *
 * leaf 모듈 — 다른 프로젝트 모듈을 import 하지 않는다(순환 방지, feedback_circular_import_colors_trading).
 */
export const SEMANTIC_COLORS = {
  success: {
    text: "text-[var(--success)]",
    bg: "bg-[var(--success)]",
    bgSoft: "bg-[var(--success)]/10",
    border: "border-[var(--success)]",
    borderSoft: "border-[var(--success)]/30",
  },
  warning: {
    text: "text-[var(--warning)]",
    bg: "bg-[var(--warning)]",
    bgSoft: "bg-[var(--warning)]/10",
    border: "border-[var(--warning)]",
    borderSoft: "border-[var(--warning)]/30",
  },
  info: {
    text: "text-[var(--info)]",
    bg: "bg-[var(--info)]",
    bgSoft: "bg-[var(--info)]/10",
    border: "border-[var(--info)]",
    borderSoft: "border-[var(--info)]/30",
  },
  danger: {
    text: "text-[var(--danger)]",
    bg: "bg-[var(--danger)]",
    bgSoft: "bg-[var(--danger)]/10",
    border: "border-[var(--danger)]",
    borderSoft: "border-[var(--danger)]/30",
  },
} as const;

export type SemanticAccent = (typeof SEMANTIC_COLORS)[keyof typeof SEMANTIC_COLORS];
