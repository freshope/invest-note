import { format } from "date-fns";

/** ISO 문자열 → 'yyyy-MM-dd HH:mm'. null/파싱 실패 시 '-'. */
export function fmtDateTime(v: unknown): string {
  if (typeof v !== "string" || !v) return "-";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : format(d, "yyyy-MM-dd HH:mm");
}

/** ISO date → 'yyyy-MM-dd'. */
export function fmtDate(v: unknown): string {
  if (typeof v !== "string" || !v) return "-";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : format(d, "yyyy-MM-dd");
}

/** 표시용 문자열(null/undefined → '-'). */
export function fmtText(v: unknown): string {
  if (v == null || v === "") return "-";
  return String(v);
}

/** 숫자 표시(로캘 구분기호). BE numeric 은 문자열일 수 있어 Number 변환 후 포맷. */
export function fmtNum(v: unknown): string {
  if (v == null || v === "") return "-";
  const n = Number(v);
  return isNaN(n) ? String(v) : n.toLocaleString();
}
