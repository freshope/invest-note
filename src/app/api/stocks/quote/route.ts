import { NextResponse, type NextRequest } from "next/server";
import { fetchKRPrice, fetchUSPrices } from "@/lib/quotes";

export type { QuoteResult } from "@/lib/quotes";

export async function GET(request: NextRequest) {
  const raw = request.nextUrl.searchParams.get("symbols");
  if (!raw) return NextResponse.json({});

  const entries = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const [code, country] = s.split(":");
      return { code: code?.slice(0, 20) ?? "", country: country ?? "KR", key: s };
    })
    .filter((e) => e.code.length > 0);

  if (entries.length === 0) return NextResponse.json({});

  const krEntries = entries.filter((e) => e.country === "KR");
  const usEntries = entries.filter((e) => e.country === "US");

  const [krResults, usBatch] = await Promise.all([
    Promise.all(krEntries.map((e) => fetchKRPrice(e.code))),
    fetchUSPrices(usEntries.map((e) => e.code)),
  ]);

  const out: Record<string, unknown> = {};
  krEntries.forEach((e, i) => { out[e.key] = krResults[i]; });
  usEntries.forEach((e) => { out[e.key] = usBatch[e.code] ?? null; });
  entries.filter((e) => e.country !== "KR" && e.country !== "US").forEach((e) => { out[e.key] = null; });

  return NextResponse.json(out);
}
