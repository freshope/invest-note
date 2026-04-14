'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { formatKRW, formatPnL, formatDate } from '@/lib/format'
import { Skeleton } from '@/components/ui/Skeleton'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'
import type { Trade, Journal, Holding, MarketType } from '@/types/database'

interface TradeWithJournal extends Trade {
  journal: Journal | null
  accountName?: string
}

interface HoldingWithPrice extends Holding {
  currentPrice?: number
  pnlAmount: number
  pnlPercent: number
  currentValue: number
}

export function StockDetail({ ticker, market }: { ticker: string; market: MarketType }) {
  const router = useRouter()
  const supabase = createClient()
  const [trades, setTrades] = useState<TradeWithJournal[]>([])
  const [holdings, setHoldings] = useState<HoldingWithPrice[]>([])
  const [stockName, setStockName] = useState('')
  const [loading, setLoading] = useState(true)
  const [priceLoading, setPriceLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const [{ data: tradeData }, { data: journalData }, { data: holdingData }] = await Promise.all([
      supabase
        .from('trades')
        .select('*, accounts!inner(name)')
        .eq('ticker', ticker)
        .eq('market', market)
        .eq('is_cancelled', false)
        .order('traded_at', { ascending: false })
        .order('created_at', { ascending: false }),
      supabase
        .from('journals')
        .select('*')
        .eq('ticker', ticker)
        .eq('market', market),
      supabase
        .from('holdings')
        .select('*')
        .eq('ticker', ticker)
        .eq('market', market)
        .gt('quantity', 0),
    ])

    // journals를 trade_id 기준으로 Map
    const journalMap = new Map<string, Journal>()
    for (const j of (journalData || [])) {
      if (j.trade_id) journalMap.set(j.trade_id, j)
    }

    const tradesWithJournal: TradeWithJournal[] = (tradeData || []).map((t: Trade & { accounts?: { name: string } }) => ({
      ...t,
      journal: journalMap.get(t.id) ?? null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      accountName: (t as any).accounts?.name,
    }))

    setTrades(tradesWithJournal)

    const holdingsWithPnl: HoldingWithPrice[] = (holdingData || []).map((h: Holding) => ({
      ...h,
      currentValue: h.avg_price * h.quantity,
      pnlAmount: 0,
      pnlPercent: 0,
    }))
    setHoldings(holdingsWithPnl)

    // 종목명 추출
    const name = (tradeData?.[0] as Trade | undefined)?.name || holdingData?.[0]?.name || ticker
    setStockName(name)

    setLoading(false)

    // 현재가 조회
    if ((holdingData || []).length > 0) {
      setPriceLoading(true)
      try {
        const res = await fetch('/api/prices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tickers: [{ ticker, market }] }),
        })
        const prices = await res.json()
        const p = prices[ticker]
        if (p) {
          setHoldings(prev => prev.map(h => {
            const currentValue = p.price * h.quantity
            const costValue = h.avg_price * h.quantity
            return {
              ...h,
              currentPrice: p.price,
              currentValue,
              pnlAmount: currentValue - costValue,
              pnlPercent: costValue > 0 ? ((currentValue - costValue) / costValue) * 100 : 0,
            }
          }))
        }
      } catch (e) {
        console.error('현재가 조회 실패:', e)
      }
      setPriceLoading(false)
    }
  }, [supabase, ticker, market])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <div className="min-h-screen bg-white">
        <div className="flex items-center gap-3 px-5 pt-6 pb-4">
          <button onClick={() => router.back()} className="w-11 h-11 flex items-center justify-center text-[#1A1A1A]">
            <ArrowLeft size={22} />
          </button>
          <Skeleton className="h-6 w-32" />
        </div>
        <div className="px-5 space-y-3">
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-20 w-full rounded-2xl" />
          <Skeleton className="h-20 w-full rounded-2xl" />
        </div>
      </div>
    )
  }

  // 보유 현황 합산
  const totalQuantity = holdings.reduce((s, h) => s + h.quantity, 0)
  const totalCurrentValue = holdings.reduce((s, h) => s + h.currentValue, 0)
  const totalCostValue = holdings.reduce((s, h) => s + h.avg_price * h.quantity, 0)
  const totalPnlAmount = totalCurrentValue - totalCostValue
  const totalPnlPercent = totalCostValue > 0 ? (totalPnlAmount / totalCostValue) * 100 : 0
  const avgPrice = totalQuantity > 0 ? totalCostValue / totalQuantity : 0
  const currentPrice = holdings[0]?.currentPrice
  const { colorClass: pnlColorClass } = formatPnL(totalPnlAmount, totalPnlPercent)
  const pnlSign = totalPnlAmount >= 0 ? '+' : ''

  return (
    <div className="min-h-screen bg-white pb-28">
      {/* 헤더 */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-4">
        <button onClick={() => router.back()} className="w-11 h-11 flex items-center justify-center text-[#1A1A1A]">
          <ArrowLeft size={22} />
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-bold text-[#1A1A1A]">{stockName}</h1>
          <p className="text-xs text-[#8B95A1]">{ticker}</p>
        </div>
        <span className={clsx(
          'px-2.5 py-1 rounded-full text-xs font-bold',
          market === 'KR' ? 'bg-[#F0F4FF] text-[#3366FF]' : 'bg-[#FFF0F0] text-[#F04452]'
        )}>
          {market}
        </span>
        {priceLoading && <RefreshCw size={16} className="text-[#8B95A1] animate-spin" />}
      </div>

      <div className="px-5 space-y-4">
        {/* 보유 현황 (보유 중일 때만) */}
        {totalQuantity > 0 && (
          <div className="bg-[#F7F8FA] rounded-3xl p-5">
            <p className="text-xs font-medium text-[#8B95A1] mb-3">보유 현황</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-[#8B95A1]">보유 수량</p>
                <p className="text-sm font-bold text-[#1A1A1A] tabular">{totalQuantity.toLocaleString()}주</p>
              </div>
              <div>
                <p className="text-xs text-[#8B95A1]">평균단가</p>
                <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(avgPrice)}</p>
              </div>
              {currentPrice && (
                <div>
                  <p className="text-xs text-[#8B95A1]">현재가</p>
                  <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(currentPrice)}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-[#8B95A1]">평가손익</p>
                <p className={clsx('text-sm font-bold tabular', pnlColorClass)}>
                  {pnlSign}{formatKRW(Math.abs(totalPnlAmount))}
                </p>
                <p className={clsx('text-xs tabular', pnlColorClass)}>
                  ({pnlSign}{Math.abs(totalPnlPercent).toFixed(2)}%)
                </p>
              </div>
            </div>
          </div>
        )}

        {/* 거래 + 일지 통합 목록 */}
        {trades.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm text-[#8B95A1]">거래 내역이 없습니다</p>
          </div>
        ) : (
          <div>
            <p className="text-xs font-medium text-[#8B95A1] mb-2">거래 내역</p>
            <div className="space-y-3">
              {trades.map(trade => (
                <TradeCard
                  key={trade.id}
                  trade={trade}
                  onTap={() => router.push(`/records/${trade.id}`)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function TradeCard({ trade, onTap }: { trade: TradeWithJournal; onTap: () => void }) {
  const isBuy = trade.trade_type === 'buy'
  const { journal } = trade
  const totalAmount = trade.price * trade.quantity

  return (
    <button
      onClick={onTap}
      className="w-full text-left bg-[#F7F8FA] rounded-2xl overflow-hidden"
    >
      {/* 거래 정보 */}
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0',
            isBuy ? 'bg-[#F04452]' : 'bg-[#1B6AC9]'
          )}>
            {isBuy ? '매수' : '매도'}
          </div>
          <div>
            <p className="text-sm font-semibold text-[#1A1A1A]">{formatDate(trade.traded_at)}</p>
            <p className="text-xs text-[#8B95A1]">
              {trade.quantity.toLocaleString()}주 @{formatKRW(trade.price)}
              {trade.accountName ? ` · ${trade.accountName}` : ''}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(totalAmount)}</p>
        </div>
      </div>

      {/* 일지 (있을 때만) */}
      {journal && (
        <div className="mx-4 mb-4 pt-3 border-t border-[#E5E8EB]">
          {journal.reason && (
            <p className="text-xs text-[#1A1A1A] mb-1.5 line-clamp-2">
              <span className="text-[#8B95A1]">이유: </span>{journal.reason}
            </p>
          )}
          {journal.reflection && (
            <p className="text-xs text-[#1A1A1A] mb-1.5 line-clamp-2">
              <span className="text-[#8B95A1]">회고: </span>{journal.reflection}
            </p>
          )}
          <div className="flex items-center gap-2 mt-1">
            {journal.target_price && (
              <span className="text-xs text-[#8B95A1]">목표 {formatKRW(journal.target_price)}</span>
            )}
            {journal.stop_loss_price && (
              <span className="text-xs text-[#8B95A1]">손절 {formatKRW(journal.stop_loss_price)}</span>
            )}
          </div>
          {journal.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {journal.tags.map(tag => (
                <span key={tag} className="px-2 py-0.5 bg-[#F0F4FF] text-[#3366FF] rounded-full text-xs">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </button>
  )
}
