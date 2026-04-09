import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

// 캐시: Map<ticker, {price, updatedAt}>
const priceCache = new Map<string, { price: number; updatedAt: string }>()
const CACHE_TTL_MS = 15 * 60 * 1000 // 15분

async function fetchKRXPrice(ticker: string): Promise<number | null> {
  try {
    // KRX Open API (15분 지연)
    const url = `https://m.stock.naver.com/api/stock/${ticker}/basic`
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      next: { revalidate: 900 },
    })
    if (!res.ok) return null
    const data = await res.json()
    return data.closePrice ? parseFloat(data.closePrice.replace(/,/g, '')) : null
  } catch {
    return null
  }
}

async function fetchYahooPrice(ticker: string): Promise<number | null> {
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}?interval=1d&range=1d`
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      next: { revalidate: 900 },
    })
    if (!res.ok) return null
    const data = await res.json()
    const result = data.chart?.result?.[0]
    return result?.meta?.regularMarketPrice ?? null
  } catch {
    return null
  }
}

export async function POST(request: NextRequest) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()
  const tickers: { ticker: string; market: string }[] = body.tickers || []

  const result: Record<string, { price: number; updatedAt: string; stale?: boolean }> = {}

  await Promise.all(
    tickers.map(async ({ ticker, market }) => {
      const cached = priceCache.get(ticker)
      const now = Date.now()
      const cacheAge = cached ? now - new Date(cached.updatedAt).getTime() : Infinity

      // 캐시 유효 (15분 이내)
      if (cached && cacheAge < CACHE_TTL_MS) {
        result[ticker] = { ...cached, stale: false }
        return
      }

      // 신선한 데이터 조회
      let price: number | null = null

      if (market === 'KR') {
        price = await fetchKRXPrice(ticker)
      } else {
        price = await fetchYahooPrice(ticker)
      }

      if (price) {
        const updatedAt = new Date().toISOString()
        priceCache.set(ticker, { price, updatedAt })
        result[ticker] = { price, updatedAt, stale: false }
      } else if (cached) {
        // 조회 실패 시 캐시된 값 사용 (stale 표시)
        result[ticker] = { ...cached, stale: true }
      }
      // 둘 다 없으면 결과에 포함하지 않음
    })
  )

  return NextResponse.json(result)
}
