/**
 * 계좌번호 정규화 — 내역서 계좌번호(account_hint)와 사용자 계좌(account_number)의 동일성 비교용.
 * 저장은 raw 원문을 유지하고, 비교 시점에만 양쪽을 정규화해 하이픈·공백·구분자 차이를 흡수한다.
 * 규칙: 숫자만 남긴다. null/빈 값은 "" 반환(null-safe — throw 금지).
 */
export function normalizeAccountNumber(value: string | null | undefined): string {
  if (!value) return "";
  return value.replace(/\D/g, "");
}

/**
 * 내역서 계좌번호(hint)와 정규화 동일성으로 사용자 계좌를 찾는다.
 * ★empty 오탐 방지: hint 가 비었거나 계좌 번호가 비었으면 매칭하지 않는다
 * (기존 계좌 대부분 account_number=null 이므로, "" === "" 오매칭 시 엉뚱한 계좌에 조용히 붙는다).
 */
export function findAccountByHint<T extends { account_number: string | null }>(
  accounts: T[],
  hint: string | null | undefined,
): T | null {
  const nh = normalizeAccountNumber(hint);
  if (!nh) return null;
  return (
    accounts.find((a) => {
      const n = normalizeAccountNumber(a.account_number);
      return n !== "" && n === nh;
    }) ?? null
  );
}
