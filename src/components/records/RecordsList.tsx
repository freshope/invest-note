'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { formatDate, formatKRW } from '@/lib/format'
import { Skeleton } from '@/components/ui/Skeleton'
import { Plus, BookOpen } from 'lucide-react'
import { clsx } from 'clsx'
import type { Trade } from '@/types/database'

export function RecordsList() {
  const router = useRouter()
  const supabase = createClient()
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    const { data } = await supabase
      .from('trades')
      .select('*')
      .eq('is_cancelled', false)
      .order('traded_at', { ascending: false })
      .order('created_at', { ascending: false })
      .limit(100)

    setTrades(data || [])
    setLoading(false)
  }, [supabase])

  useEffect(() => { load() }, [load])

  return (
    <div className="min-h-screen bg-white">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 pt-6 pb-4">
        <h1 className="text-xl font-bold text-[#1A1A1A]">기록</h1>
        <button
          onClick={() => router.push('/records/new')}
          className="w-10 h-10 flex items-center justify-center bg-[#3366FF] text-white rounded-full"
        >
          <Plus size={20} strokeWidth={2.5} />
        </button>
      </div>

      {loading ? (
        <div className="px-5 space-y-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full rounded-2xl" />)}
        </div>
      ) : trades.length === 0 ? (
        <div className="flex flex-col items-center justify-center pt-24 text-center px-8">
          <BookOpen size={48} className="text-[#E5E8EB] mb-4" />
          <h2 className="text-base font-bold text-[#1A1A1A] mb-2">첫 거래를 기록해 보세요</h2>
          <p className="text-sm text-[#8B95A1] mb-6">매매 내역을 기록하면<br />투자 습관이 만들어집니다</p>
          <button
            onClick={() => router.push('/records/new')}
            className="px-6 py-3 bg-[#3366FF] text-white rounded-2xl text-sm font-semibold"
          >
            거래 기록하기
          </button>
        </div>
      ) : (
        <div className="px-5">
          {/* 날짜별 그룹 */}
          {groupByDate(trades).map(({ date, items }) => (
            <div key={date} className="mb-4">
              <p className="text-xs font-medium text-[#8B95A1] mb-2">{formatDate(date)}</p>
              <div className="space-y-2">
                {items.map(trade => (
                  <TradeItem key={trade.id} trade={trade} onTap={() => router.push(`/records/${trade.id}`)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TradeItem({ trade, onTap }: { trade: Trade; onTap: () => void }) {
  const isBuy = trade.trade_type === 'buy'
  return (
    <button
      onClick={onTap}
      className="w-full flex items-center justify-between py-3 px-4 bg-[#F7F8FA] rounded-2xl"
    >
      <div className="flex items-center gap-3">
        <div className={clsx(
          'w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white',
          isBuy ? 'bg-[#F04452]' : 'bg-[#1B6AC9]'
        )}>
          {isBuy ? '매수' : '매도'}
        </div>
        <div className="text-left">
          <p className="text-sm font-semibold text-[#1A1A1A]">{trade.name || trade.ticker}</p>
          <p className="text-xs text-[#8B95A1]">{trade.ticker} · {trade.quantity.toLocaleString()}주</p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-sm font-bold text-[#1A1A1A] tabular">{formatKRW(trade.price * trade.quantity)}</p>
        <p className="text-xs text-[#8B95A1] tabular">@{formatKRW(trade.price)}</p>
      </div>
    </button>
  )
}

function groupByDate(trades: Trade[]) {
  const map = new Map<string, Trade[]>()
  for (const t of trades) {
    const date = t.traded_at
    if (!map.has(date)) map.set(date, [])
    map.get(date)!.push(t)
  }
  return Array.from(map.entries()).map(([date, items]) => ({ date, items }))
}
