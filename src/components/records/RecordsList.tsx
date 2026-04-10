'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { formatDate, formatKRW } from '@/lib/format'
import { Skeleton } from '@/components/ui/Skeleton'
import { Plus, BookOpen } from 'lucide-react'
import { clsx } from 'clsx'
import type { Trade, Account } from '@/types/database'
import { useAccountFilter } from '@/hooks/useAccountFilter'
import { AccountFilterDropdown } from '@/components/ui/AccountFilterDropdown'

const PAGE_SIZE = 50

export function RecordsList() {
  const router = useRouter()
  const supabase = createClient()
  const [trades, setTrades] = useState<Trade[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const { selectedAccountId, setSelectedAccountId } = useAccountFilter()
  const requestId = useRef(0)

  const loadAccounts = useCallback(async () => {
    const { data } = await supabase.from('accounts').select('*').is('deleted_at', null).order('created_at')
    setAccounts(data || [])
  }, [supabase])

  const loadTrades = useCallback(async (accountId: string, offset: number, append: boolean) => {
    const id = ++requestId.current
    const query = supabase
      .from('trades')
      .select('*')
      .eq('is_cancelled', false)
      .order('traded_at', { ascending: false })
      .order('created_at', { ascending: false })
      .range(offset, offset + PAGE_SIZE - 1)

    if (accountId !== 'all') {
      query.eq('account_id', accountId)
    }

    const { data } = await query
    if (id !== requestId.current) return  // discard stale response from previous filter
    const rows = data || []
    setHasMore(rows.length === PAGE_SIZE)
    if (append) {
      setTrades(prev => [...prev, ...rows])
    } else {
      setTrades(rows)
    }
  }, [supabase])

  const load = useCallback(async () => {
    setLoading(true)
    await Promise.all([loadAccounts(), loadTrades(selectedAccountId, 0, false)])
    setLoading(false)
  }, [loadAccounts, loadTrades, selectedAccountId])

  const loadMore = useCallback(async () => {
    setLoadingMore(true)
    await loadTrades(selectedAccountId, trades.length, true)
    setLoadingMore(false)
  }, [loadTrades, selectedAccountId, trades.length])

  useEffect(() => { load() }, [load])

  // Reset stale filter if stored account was deleted
  useEffect(() => {
    if (accounts.length > 0 && selectedAccountId !== 'all' && !accounts.find(a => a.id === selectedAccountId)) {
      setSelectedAccountId('all')
    }
  }, [accounts, selectedAccountId, setSelectedAccountId])

  return (
    <div className="min-h-screen bg-white">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 pt-6 pb-4">
        <AccountFilterDropdown
          accounts={accounts}
          selectedAccountId={selectedAccountId}
          onSelect={setSelectedAccountId}
        />
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
                  <TradeItem
                    key={trade.id}
                    trade={trade}
                    account={accounts.find(a => a.id === trade.account_id)}
                    onTap={() => router.push(`/records/${trade.id}`)}
                  />
                ))}
              </div>
            </div>
          ))}
          {hasMore && (
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="w-full py-3 text-sm text-[#3366FF] font-medium disabled:opacity-50"
            >
              {loadingMore ? '불러오는 중...' : '더 보기'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function TradeItem({ trade, account, onTap }: { trade: Trade; account?: Account; onTap: () => void }) {
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
          <p className="text-xs text-[#8B95A1]">
            {trade.ticker} · {trade.quantity.toLocaleString()}주
            {account ? ` · ${account.name}` : ''}
          </p>
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
