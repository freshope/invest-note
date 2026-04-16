import { NextResponse, type NextRequest } from "next/server";

interface StockResult {
  code: string;
  name: string;
  market: "KR" | "US" | "OTHER";
  exchange: string;
}

// 한글 포함 여부 — KR 검색 경로 결정
function hasKorean(str: string): boolean {
  return /[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]/.test(str);
}

// 6자리 숫자 — 한국 종목코드
function isKrCode(str: string): boolean {
  return /^\d{6}$/.test(str.trim());
}

// 네이버 증권 자동완성 — 한국 주식 검색
async function searchKR(q: string): Promise<StockResult[]> {
  try {
    const url = `https://ac.stock.naver.com/ac?q=${encodeURIComponent(q)}&target=stock`;
    const res = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];

    const data: { items?: { code: string; name: string; typeCode: string }[] } = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];

    // 종목코드 whitelist: 경로 순회 방지
    const CODE_RE = /^[A-Z0-9]{4,9}$/i;
    return items
      .filter(({ code, name }) =>
        typeof code === "string" &&
        typeof name === "string" &&
        CODE_RE.test(code)
      )
      .slice(0, 10)
      .map(({ code, name, typeCode }) => ({
        code: code.slice(0, 20),
        name: name.slice(0, 50),
        market: "KR" as const,
        exchange: typeCode || "KR",
      }));
  } catch {
    return [];
  }
}

// Yahoo Finance — 해외 주식 검색 (영문 쿼리)
async function searchUS(q: string): Promise<StockResult[]> {
  const EXCHANGE_MAP: Record<string, string> = {
    NMS: "NASDAQ", NGM: "NASDAQ", NCM: "NASDAQ",
    NYQ: "NYSE", NYS: "NYSE",
    PCX: "NYSE ARCA",
    ASE: "AMEX",
    BTS: "CBOE",
  };

  try {
    const url = new URL("https://query2.finance.yahoo.com/v1/finance/search");
    url.searchParams.set("q", q);
    url.searchParams.set("quotesCount", "10");
    url.searchParams.set("newsCount", "0");
    url.searchParams.set("listsCount", "0");

    const res = await fetch(url.toString(), {
      headers: { "User-Agent": "Mozilla/5.0" },
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];

    const data: { quotes?: { symbol: string; shortname?: string; longname?: string; exchange: string; quoteType: string }[] } = await res.json();
    const quotes = Array.isArray(data.quotes) ? data.quotes : [];

    return quotes
      .filter((q) => (q.quoteType === "EQUITY" || q.quoteType === "ETF") && q.exchange in EXCHANGE_MAP)
      .slice(0, 10)
      .map((q) => ({
        code: q.symbol,
        name: (q.shortname || q.longname || q.symbol).slice(0, 50),
        market: "US" as const,
        exchange: EXCHANGE_MAP[q.exchange] ?? q.exchange,
      }));
  } catch {
    return [];
  }
}

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim();
  if (!q || q.length < 1) return NextResponse.json([]);
  if (q.length > 100) return NextResponse.json([]);

  // 한글이거나 6자리 숫자 → 네이버(KR)
  // 그 외 영문 → Yahoo Finance(US)
  const results: StockResult[] = hasKorean(q) || isKrCode(q)
    ? await searchKR(q)
    : await searchUS(q);

  return NextResponse.json(results);
}
