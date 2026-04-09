'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { formatKRW, formatPnL } from '@/lib/format'
import { Skeleton } from '@/components/ui/Skeleton'
import { Settings, RefreshCw, ChevronDown } from 'lucide-react'
import type { Account, Holding } from '@/types/database'
import { clsx } from 'clsx'

interface HoldingWithPrice extends Holding {
  currentPrice?: number
  priceUpdatedAt?: string
  pnlAmount?: number
  pnlPercent?: number
}

interface AccountWithHoldings extends Account {
  holdings: HoldingWithPrice[]
  totalValue: number
  totalCost: number
}

export function HomeDashboard() {
  const router = useRouter()
  const supabase = createClient()
  const [accounts, setAccounts] = useState<AccountWithHoldings[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<string>('all')
  const [loading, setLoading] = useState(true)
  const [priceLoading, setPriceLoading] = useState(false)
  const [showAccountPicker, setShowAccountPicker] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    const { data: accountData } = await supabase
      .from('accounts')
      .select('*')
      .is('deleted_at', null)
      .order('created_at')

    const { data: holdingData } = await supabase
      .from('holdings')
      .select('*')
      .gt('quantity', 0)

    if (!accountData) { setLoading(false); return }

    const accountsWithHoldings: AccountWithHoldings[] = (accountData as Account[]).map(acc => {
      const holdings = (holdingData || []).filter(h => h.account_id === acc.id)
      return {
        ...acc,
        holdings,
        totalValue: holdings.reduce((sum, h) => sum + h.avg_price * h.quantity, 0),
        totalCost: holdings.reduce((sum, h) => sum + h.avg_price * h.quantity, 0),
      }
    })

    setAccounts(accountsWithHoldings)
    setLoading(false)

    // 현재가 조회
    const allTickers = (holdingData || [])
      .reduce((acc: {ticker: string, market: string}[], h) => {
        if (!acc.find(a => a.ticker === h.ticker)) {
          acc.push({ ticker: h.ticker, market: h.market })
        }
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

        setAccounts(prev => prev.map(acc => ({
          ...acc,
          holdings: acc.holdings.map(h => {
            const p = prices[h.ticker]
            if (!p) return h
            const currentValue = p.price * h.quantity
            const costValue = h.avg_price * h.quantity
            return {
              ...h,
              currentPrice: p.price,
              priceUpdatedAt: p.updatedAt,
              pnlAmount: currentValue - costValue,
              pnlPercent: costValue > 0 ? ((currentValue - costValue) / costValue) * 100 : 0,
            }
          }),
          totalValue: acc.holdings.reduce((sum, h) => {
            const p = prices[h.ticker]
            return sum + (p ? p.price * h.quantity : h.avg_price * h.quantity)
          }, 0),
        })))
      } catch (e) {
        console.error('현재가 조회 실패:', e)
      }
      setPriceLoading(false)
    }
  }, [supabase])

  useEffect(() => { loadData() }, [loadData])

  // 선택 계좌 필터
  const filteredAccounts = selectedAccountId === 'all' ? accounts : accounts.filter(a => a.id === selectedAccountId)
  const totalValue = filteredAccounts.reduce((sum, a) => sum + a.totalValue, 0)
  const totalCost = filteredAccounts.reduce((sum, a) => sum + a.totalCost, 0)
  const totalPnL = totalValue - totalCost
  const totalPnLPercent = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0
  const { amount: pnlAmount, percent: pnlPercent, colorClass } = formatPnL(totalPnL, totalPnLPercent)

  // 상위 3개 보유 종목 (평가금액 기준)
  const topHoldings = filteredAccounts
    .flatMap(a => a.holdings)
    .sort((a, b) => ((b.currentPrice || b.avg_price) * b.quantity) - ((a.currentPrice || a.avg_price) * a.quantity))
    .slice(0, 3)

  const selectedAccountName = selectedAccountId === 'all'
    ? '전체 계좌'
    : accounts.find(a => a.id === selectedAccountId)?.name || '전체 계좌'

  if (loading) {
    return (
      <div className="px-5 pt-6 space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-6 w-40" />
        <div className="mt-6 space-y-3">
          <Skeleton className="h-20 w-full rounded-2xl" />
          <Skeleton className="h-20 w-full rounded-2xl" />
        </div>
      </div>
    )
  }

  if (accounts.length === 0) {
    return (
      <div className="px-5 pt-6">
        <div className="flex justify-end mb-10">
          <button onClick={() => router.push('/settings')} className="w-8 h-8 flex items-center justify-center text-[#8B95A1]">
            <Settings size={20} />
          </button>
        </div>
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-[#F7F8FA] rounded-full flex items-center justify-center mb-4">
            <span className="text-3xl">📊</span>
          </div>
          <h2 className="text-lg font-bold text-[#1A1A1A] mb-2">아직 계좌가 없어요</h2>
          <p className="text-sm text-[#8B95A1] mb-6">계좌를 추가하고 투자를 시작해 보세요</p>
          <button
            onClick={() => router.push('/settings')}
            className="px-6 py-3 bg-[#3366FF] text-white rounded-2xl text-sm font-semibold"
          >
            계좌 추가하기
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      {/* 상단 헤더 */}
      <div className="flex items-center justify-between px-5 pt-6 pb-2">
        <button
          onClick={() => setShowAccountPicker(!showAccountPicker)}
          className="flex items-center gap-1 text-sm font-medium text-[#1A1A1A]"
        >
          {selectedAccountName}
          <ChevronDown size={14} className={clsx('transition-transform', showAccountPicker && 'rotate-180')} />
        </button>
        <div className="flex items-center gap-2">
          {priceLoading && <RefreshCw size={16} className="text-[#8B95A1] animate-spin" />}
          <button onClick={() => router.push('/settings')} className="w-8 h-8 flex items-center justify-center text-[#8B95A1]">
            <Settings size={20} />
          </button>
        </div>
      </div>

      {/* 계좌 선택 드롭다운 */}
      {showAccountPicker && (
        <div className="mx-5 mb-2 bg-white border border-[#E5E8EB] rounded-2xl shadow-lg overflow-hidden">
          {[{ id: 'all', name: '전체 계좌' }, ...accounts.map(a => ({ id: a.id, name: a.name }))].map(item => (
            <button
              key={item.id}
              onClick={() => { setSelectedAccountId(item.id); setShowAccountPicker(false) }}
              className={clsx(
                'w-full text-left px-4 py-3 text-sm',
                selectedAccountId === item.id ? 'text-[#3366FF] font-semibold bg-[#F0F4FF]' : 'text-[#1A1A1A]'
              )}
            >
              {item.name}
            </button>
          ))}
        </div>
      )}

      {/* 총 평가금액 */}
      <div className="px-5 pt-4 pb-2">
        <p className="text-xs text-[#8B95A1] mb-1">총 평가금액</p>
        <p className="text-4xl font-bold text-[#1A1A1A] tabular">{formatKRW(totalValue)}</p>
        <p className={clsx('text-base font-semibold tabular mt-1', colorClass)}>
          {pnlAmount} ({pnlPercent})
        </p>
      </div>

      {/* 계좌별 스냅샷 */}
      <div className="px-5 mt-4">
        <p className="text-xs font-medium text-[#8B95A1] mb-2">계좌</p>
        <div className="space-y-2">
          {filteredAccounts.map(acc => {
            const accPnL = acc.totalValue - acc.totalCost
            const accPnLPercent = acc.totalCost > 0 ? (accPnL / acc.totalCost) * 100 : 0
            const { amount, percent, colorClass: c } = formatPnL(accPnL, accPnLPercent)
            return (
              <div key={acc.id} className="flex items-center justify-between py-3 px-4 bg-[#F7F8FA] rounded-2xl">
                <div>
                  <p className="text-sm font-semibold text-[#1A1A1A]">{acc.name}</p>
                  <p className="text-xs text-[#8B95A1]">{acc.broker}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(acc.totalValue)}</p>
                  <p className={clsx('text-xs tabular', c)}>{amount} ({percent})</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 보유 종목 상위 3개 */}
      {topHoldings.length > 0 && (
        <div className="px-5 mt-4">
          <p className="text-xs font-medium text-[#8B95A1] mb-2">주요 보유 종목</p>
          <div className="space-y-1">
            {topHoldings.map(h => {
              const value = (h.currentPrice || h.avg_price) * h.quantity
              const cost = h.avg_price * h.quantity
              const pnl = value - cost
              const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
              const { colorClass: c } = formatPnL(pnl, pnlPct)
              const sign = pnl >= 0 ? '+' : '-'
              return (
                <div key={`${h.account_id}-${h.ticker}`} className="flex items-center justify-between py-2.5 border-b border-[#F0F0F0] last:border-0">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-[#F0F4FF] flex items-center justify-center">
                      <span className="text-xs font-bold text-[#3366FF]">{h.ticker.slice(0, 2)}</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[#1A1A1A]">{h.name || h.ticker}</p>
                      <p className="text-xs text-[#8B95A1]">{h.quantity.toLocaleString()}주</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(value)}</p>
                    <p className={clsx('text-xs tabular', c)}>
                      {sign}{formatKRW(Math.abs(pnl))} ({sign}{Math.abs(pnlPct).toFixed(2)}%)
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 고정 하단 CTA */}
      <div className="px-5 mt-6">
        <button
          onClick={() => router.push('/records/new')}
          className="w-full py-4 bg-[#3366FF] text-white rounded-2xl text-sm font-bold"
        >
          오늘 거래 기록하기
        </button>
      </div>
    </div>
  )
}
