import type { QuoteMap } from "@/lib/portfolio";

export interface QuoteResult {
  price: number;
  currency: string;
  asOf: string;
}

export async function fetchKRPrice(code: string): Promise<QuoteResult | null> {
  try {
    const url = `https://polling.finance.naver.com/api/realtime/domestic/stock/${encodeURIComponent(code)}`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 60 },
    });
    if (res.ok) {
      const data = await res.json();
      const item = data?.datas?.[0] ?? data?.data ?? data;
      // closePriceRaw는 쉼표 없는 숫자 문자열, closePrice는 "216,500" 형태라 NaN
      const price = Number(item?.closePriceRaw ?? item?.now ?? item?.closePrice?.replace?.(/,/g, ""));
      if (price > 0) return { price, currency: "KRW", asOf: new Date().toISOString() };
    }
  } catch {
    // fall through to backup
  }

  // 백업: stock basic API
  try {
    const url = `https://api.stock.naver.com/stock/${encodeURIComponent(code)}/basic`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 60 },
    });
    if (res.ok) {
      const data = await res.json();
      // stockEndPrice는 쉼표 포함 가능, 쉼표 제거 후 파싱
      const raw = data?.closePriceRaw ?? data?.stockEndPrice?.replace?.(/,/g, "") ?? data?.closePrice?.replace?.(/,/g, "");
      const price = Number(raw);
      if (price > 0) return { price, currency: "KRW", asOf: new Date().toISOString() };
    }
  } catch {
    // ignore
  }

  return null;
}

// Yahoo Finance v7 batch API가 차단됨 → v8 chart API로 개별 조회
async function fetchUSPrice(symbol: string): Promise<QuoteResult | null> {
  try {
    const url = `https://query2.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    const data = await res.json();
    const meta = data?.chart?.result?.[0]?.meta;
    const price = Number(meta?.regularMarketPrice);
    if (price > 0) {
      return { price, currency: meta?.currency ?? "USD", asOf: new Date().toISOString() };
    }
  } catch {
    // ignore
  }
  return null;
}

export async function fetchUSPrices(
  symbols: string[],
): Promise<Record<string, QuoteResult | null>> {
  if (symbols.length === 0) return {};
  const results = await Promise.all(symbols.map((s) => fetchUSPrice(s)));
  return Object.fromEntries(symbols.map((s, i) => [s, results[i]]));
}

/** `keys` 형식: "종목코드:국가" (예: "005930:KR", "AAPL:US") */
export async function fetchQuotesByKeys(keys: string[]): Promise<QuoteMap> {
  if (keys.length === 0) return {};

  const entries = keys.map((key) => {
    const [code, country] = key.split(":");
    return { code: code?.slice(0, 20) ?? "", country: country ?? "KR", key };
  }).filter((e) => e.code.length > 0);

  const krEntries = entries.filter((e) => e.country === "KR");
  const usEntries = entries.filter((e) => e.country === "US");

  const [krResults, usBatch] = await Promise.all([
    Promise.all(krEntries.map((e) => fetchKRPrice(e.code))),
    fetchUSPrices(usEntries.map((e) => e.code)),
  ]);

  const out: QuoteMap = {};
  krEntries.forEach((e, i) => {
    out[e.key] = krResults[i];
  });
  usEntries.forEach((e) => {
    out[e.key] = usBatch[e.code] ?? null;
  });
  entries
    .filter((e) => e.country !== "KR" && e.country !== "US")
    .forEach((e) => {
      out[e.key] = null;
    });

  return out;
}
