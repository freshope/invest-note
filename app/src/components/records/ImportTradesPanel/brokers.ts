export const BROKER_OPTIONS = [
  { key: "samsung_xlsx", label: "삼성증권", accept: ".xlsx,.xls" },
  { key: "toss_pdf", label: "토스증권", accept: ".pdf" },
] as const;

export type BrokerKey = (typeof BROKER_OPTIONS)[number]["key"];

export const BROKER_NAMES: Record<string, string> = Object.fromEntries(
  BROKER_OPTIONS.map((b) => [b.key, b.label])
);
