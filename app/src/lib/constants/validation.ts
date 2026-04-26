// 폼 입력 길이 제한 (백엔드 schema 한도와 동일하게 유지)
export const VALIDATION_LIMITS = {
  ACCOUNT_NAME_MAX: 50,
  ASSET_NAME_MAX: 100,
  EXCHANGE_MAX: 50,
  TRADE_FREE_TEXT_MAX: 5000,
} as const;
