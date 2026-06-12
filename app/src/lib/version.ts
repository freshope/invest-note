/** semver "a.b.c" 비교. a<b → -1, a==b → 0, a>b → 1. 자릿수가 다르면 0으로 패딩. */
export function compareVersions(a: string, b: string): -1 | 0 | 1 {
  const pa = a.split(".").map((n) => Number.parseInt(n, 10) || 0);
  const pb = b.split(".").map((n) => Number.parseInt(n, 10) || 0);
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i += 1) {
    const x = pa[i] ?? 0;
    const y = pb[i] ?? 0;
    if (x < y) return -1;
    if (x > y) return 1;
  }
  return 0;
}

/** 현재 버전이 최소 지원 버전보다 낮으면 강제 업데이트 필요. 둘 중 하나라도 비면 강제하지 않음(no-force). */
export function isUpdateRequired(current: string, min: string): boolean {
  if (!current || !min) return false;
  return compareVersions(current, min) < 0;
}
