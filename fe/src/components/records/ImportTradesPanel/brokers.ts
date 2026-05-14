export const BROKER_OPTIONS = [
  { key: "samsung_xlsx", label: "삼성증권", accept: ".xlsx,.xls" },
  { key: "toss_pdf", label: "토스증권", accept: ".pdf" },
] as const;

export type BrokerKey = (typeof BROKER_OPTIONS)[number]["key"];

export function findBrokerKeyByAccountBroker(
  broker: string | null | undefined
): BrokerKey | null {
  if (!broker) return null;
  const matched = BROKER_OPTIONS.find((b) => b.label === broker);
  return matched ? matched.key : null;
}
