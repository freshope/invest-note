'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase/client'
import { formatKRW, formatPnL } from '@/lib/format'
import { Skeleton } from '@/components/ui/Skeleton'
import { clsx } from 'clsx'
import { RefreshCw } from 'lucide-react'
import type { Account, Holding } from '@/types/database'
import { useAccountFilter } from '@/hooks/useAccountFilter'
import { AccountFilterDropdown } from '@/components/ui/AccountFilterDropdown'

interface HoldingWithPrice extends Holding {
  currentPrice?: number
  priceStale?: boolean
  pnlAmount: number
  pnlPercent: number
  currentValue: number
}

interface AccountWithHoldings extends Account {
  holdings: HoldingWithPrice[]
  totalValue: number
  totalCost: number
}

export function AssetsView() {
  const supabase = createClient()
  const [accounts, setAccounts] = useState<AccountWithHoldings[]>([])
  const { selectedAccountId, setSelectedAccountId } = useAccountFilter()
  const [loading, setLoading] = useState(true)
  const [priceLoading, setPriceLoading] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'weight'>('list')

  const load = useCallback(async () => {
    setLoading(true)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: accountData } = await supabase.from('accounts').select('*').is('deleted_at', null).order('created_at') as any
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { data: holdingData } = await supabase.from('holdings').select('*').gt('quantity', 0) as any

    if (!accountData) { setLoading(false); return }

    const accs: AccountWithHoldings[] = (accountData as Account[]).map(acc => {
      const holdings: HoldingWithPrice[] = ((holdingData || []) as Holding[]).filter(h => h.account_id === acc.id).map(h => ({
        ...h,
        currentValue: h.avg_price * h.quantity,
        pnlAmount: 0,
        pnlPercent: 0,
      }))
      const totalCost = holdings.reduce((s, h) => s + h.avg_price * h.quantity, 0)
      return { ...acc, holdings, totalValue: totalCost, totalCost }
    })

    setAccounts(accs)
    setLoading(false)

    // 현재가 로드
    const allTickers = ((holdingData || []) as Holding[]).reduce((acc: {ticker: string; market: string}[], h) => {
      if (!acc.find(a => a.ticker === h.ticker)) acc.push({ ticker: h.ticker, market: h.market })
      return acc
    }, [])

    if (allTickers.length > 0) {
      setPriceLoading(true)
      try {
        const res = await fetch('/api/prices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tickers: allTickers }),
        })
        const prices = await res.json()

        setAccounts(prev => prev.map(acc => {
          const holdings: HoldingWithPrice[] = acc.holdings.map(h => {
            const p = prices[h.ticker]
            const currentPrice = p?.price
            const currentValue = currentPrice ? currentPrice * h.quantity : h.avg_price * h.quantity
            const costValue = h.avg_price * h.quantity
            return {
              ...h,
              currentPrice,
              priceStale: p?.stale,
              currentValue,
              pnlAmount: currentValue - costValue,
              pnlPercent: costValue > 0 ? ((currentValue - costValue) / costValue) * 100 : 0,
            }
          })
          const totalValue = holdings.reduce((s, h) => s + h.currentValue, 0)
          return { ...acc, holdings, totalValue }
        }))
      } catch (e) {
        console.error('현재가 조회 실패:', e)
      }
      setPriceLoading(false)
    }
  }, [supabase])

  useEffect(() => { load() }, [load])

  // Reset stale filter if stored account was deleted
  useEffect(() => {
    if (accounts.length > 0 && selectedAccountId !== 'all' && !accounts.find(a => a.id === selectedAccountId)) {
      setSelectedAccountId('all')
    }
  }, [accounts, selectedAccountId, setSelectedAccountId])

  const filteredAccounts = selectedAccountId === 'all' ? accounts : accounts.filter(a => a.id === selectedAccountId)
  const allHoldings = filteredAccounts.flatMap(a => a.holdings)
  const totalValue = filteredAccounts.reduce((s, a) => s + a.totalValue, 0)
  const totalCost = filteredAccounts.reduce((s, a) => s + a.totalCost, 0)
  const totalPnL = totalValue - totalCost
  const totalPnLPct = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0
  const { amount: pnlAmt, percent: pnlPct, colorClass } = formatPnL(totalPnL, totalPnLPct)

  if (loading) {
    return (
      <div className="px-5 pt-6 space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-24 w-full rounded-2xl" />
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full rounded-2xl" />)}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white pb-24">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 pt-6 pb-2">
        <AccountFilterDropdown
          accounts={accounts}
          selectedAccountId={selectedAccountId}
          onSelect={setSelectedAccountId}
        />
        <div className="flex items-center gap-2">
          {priceLoading && <RefreshCw size={16} className="text-[#8B95A1] animate-spin" />}
          <button onClick={load} className="w-8 h-8 flex items-center justify-center text-[#8B95A1]">
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* 총 자산 요약 */}
      <div className="px-5 pt-2 pb-4">
        <p className="text-xs text-[#8B95A1] mb-1">총 평가금액</p>
        <p className="text-3xl font-bold text-[#1A1A1A] tabular">{formatKRW(totalValue)}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className={clsx('text-sm font-semibold tabular', colorClass)}>
            {pnlAmt} ({pnlPct})
          </span>
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-[#8B95A1]">매입금액 {formatKRW(totalCost)}</span>
        </div>
      </div>

      {/* 보기 모드 토글 */}
      <div className="flex px-5 mb-4 gap-2">
        {(['list', 'weight'] as const).map(mode => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={clsx(
              'px-4 py-1.5 rounded-full text-xs font-medium border transition-all',
              viewMode === mode ? 'bg-[#3366FF] text-white border-[#3366FF]' : 'border-[#E5E8EB] text-[#8B95A1]'
            )}
          >
            {mode === 'list' ? '목록' : '비중'}
          </button>
        ))}
      </div>

      {allHoldings.length === 0 ? (
        <div className="flex flex-col items-center justify-center pt-16 text-center px-8">
          <p className="text-sm text-[#8B95A1]">보유 종목이 없습니다.<br/>거래를 기록하면 자동으로 반영됩니다.</p>
        </div>
      ) : viewMode === 'list' ? (
        <HoldingsList holdings={allHoldings} totalValue={totalValue} />
      ) : (
        <WeightView holdings={allHoldings} totalValue={totalValue} />
      )}
    </div>
  )
}

function HoldingsList({ holdings, totalValue }: { holdings: HoldingWithPrice[]; totalValue: number }) {
  const sorted = [...holdings].sort((a, b) => b.currentValue - a.currentValue)

  return (
    <div className="px-5 space-y-2">
      {sorted.map(h => {
        const weight = totalValue > 0 ? (h.currentValue / totalValue) * 100 : 0
        const { amount, percent, colorClass } = formatPnL(h.pnlAmount, h.pnlPercent)
        const sign = h.pnlAmount >= 0 ? '+' : ''

        return (
          <div key={`${h.account_id}-${h.ticker}`} className="py-3 px-4 bg-[#F7F8FA] rounded-2xl">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-full bg-[#F0F4FF] flex items-center justify-center">
                  <span className="text-xs font-bold text-[#3366FF]">{h.ticker.slice(0, 2)}</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#1A1A1A]">{h.name || h.ticker}</p>
                  <p className="text-xs text-[#8B95A1]">{h.ticker} · {h.quantity.toLocaleString()}주</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(h.currentValue)}</p>
                <p className={clsx('text-xs tabular', colorClass)}>
                  {sign}{formatKRW(Math.abs(h.pnlAmount))} ({percent})
                </p>
              </div>
            </div>

            {/* 비중 바 */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1 bg-[#E5E8EB] rounded-full overflow-hidden">
                <div className="h-full bg-[#3366FF] rounded-full" style={{ width: `${weight}%` }} />
              </div>
              <span className="text-xs text-[#8B95A1] tabular">{weight.toFixed(1)}%</span>
            </div>

            {/* 단가 정보 */}
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-xs text-[#8B95A1]">평균단가 {formatKRW(h.avg_price)}</span>
              {h.currentPrice && (
                <span className="text-xs text-[#8B95A1]">
                  현재가 {formatKRW(h.currentPrice)}
                  {h.priceStale && <span className="ml-1 text-[#F04452]">·지연</span>}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function WeightView({ holdings, totalValue }: { holdings: HoldingWithPrice[]; totalValue: number }) {
  const sorted = [...holdings].sort((a, b) => b.currentValue - a.currentValue)
  const COLORS = ['#3366FF', '#F04452', '#1B6AC9', '#FF8C00', '#9B59B6', '#27AE60', '#E74C3C', '#3498DB']

  return (
    <div className="px-5">
      {/* 비중 바 */}
      <div className="flex h-6 rounded-full overflow-hidden mb-4">
        {sorted.map((h, i) => {
          const weight = totalValue > 0 ? (h.currentValue / totalValue) * 100 : 0
          return (
            <div
              key={`${h.account_id}-${h.ticker}`}
              style={{ width: `${weight}%`, backgroundColor: COLORS[i % COLORS.length] }}
            />
          )
        })}
      </div>

      {/* 범례 */}
      <div className="space-y-2">
        {sorted.map((h, i) => {
          const weight = totalValue > 0 ? (h.currentValue / totalValue) * 100 : 0
          return (
            <div key={`${h.account_id}-${h.ticker}`} className="flex items-center justify-between py-2.5 border-b border-[#F0F0F0] last:border-0">
              <div className="flex items-center gap-2.5">
                <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                <div>
                  <p className="text-sm font-semibold text-[#1A1A1A]">{h.name || h.ticker}</p>
                  <p className="text-xs text-[#8B95A1]">{h.quantity.toLocaleString()}주</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-[#1A1A1A] tabular">{weight.toFixed(1)}%</p>
                <p className="text-xs text-[#8B95A1] tabular">{formatKRW(h.currentValue)}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
