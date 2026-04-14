import { StockDetail } from '@/components/stocks/StockDetail'
import type { MarketType } from '@/types/database'

export default async function StockPage({ params }: { params: Promise<{ market: string; ticker: string }> }) {
  const { market, ticker } = await params
  return <StockDetail market={market as MarketType} ticker={ticker} />
}
