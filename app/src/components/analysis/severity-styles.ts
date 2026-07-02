import { AlertTriangle, Info, AlertCircle } from "lucide-react";
import { SEMANTIC_COLORS } from "@/lib/constants/semantic-colors";

// soft 배경(bgSoft)+soft 테두리(borderSoft)+solid 텍스트로 라이트/다크 자동 대응.
// 색 값은 globals.css의 semantic 토큰(:root와 .dark 블록)에서 단일 관리 — 변형 프리픽스 불필요.
export const SEVERITY_STYLES = {
  info: {
    bg: SEMANTIC_COLORS.info.bgSoft,
    border: SEMANTIC_COLORS.info.borderSoft,
    icon: Info,
    iconClass: SEMANTIC_COLORS.info.text,
    metricClass: SEMANTIC_COLORS.info.text,
  },
  warn: {
    bg: SEMANTIC_COLORS.warning.bgSoft,
    border: SEMANTIC_COLORS.warning.borderSoft,
    icon: AlertTriangle,
    iconClass: SEMANTIC_COLORS.warning.text,
    metricClass: SEMANTIC_COLORS.warning.text,
  },
  critical: {
    bg: SEMANTIC_COLORS.danger.bgSoft,
    border: SEMANTIC_COLORS.danger.borderSoft,
    icon: AlertCircle,
    iconClass: SEMANTIC_COLORS.danger.text,
    metricClass: SEMANTIC_COLORS.danger.text,
  },
} as const;
