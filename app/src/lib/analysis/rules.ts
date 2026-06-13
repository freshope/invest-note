// BE `/analysis/dashboard` 응답의 `suggestions` 필드 타입 정의.
// 규칙 평가는 BE(`api/.../domain/analysis/rules.py`)가 단독 SOT로 담당하며,
// FE는 BE 응답을 그대로 표시한다.

export interface Suggestion {
  id: string;
  severity: "info" | "warn" | "critical";
  title: string;
  body: string;
  metric?: { label: string; value: string };
  linkSection?: "strategy" | "emotion" | "tag" | "concentration" | "review";
}
