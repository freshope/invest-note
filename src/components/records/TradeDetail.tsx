'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { formatKRW, formatDate } from '@/lib/format'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { JournalForm } from './JournalForm'
import { ArrowLeft, BookOpen, XCircle } from 'lucide-react'
import { clsx } from 'clsx'
import type { Trade, Journal } from '@/types/database'
import { Skeleton } from '@/components/ui/Skeleton'

export function TradeDetail({ tradeId }: { tradeId: string }) {
  const router = useRouter()
  const supabase = createClient()
  const [trade, setTrade] = useState<Trade | null>(null)
  const [journal, setJournal] = useState<Journal | null>(null)
  const [loading, setLoading] = useState(true)
  const [showJournalSheet, setShowJournalSheet] = useState(false)
  const [showReflectionSheet, setShowReflectionSheet] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  const load = useCallback(async () => {
    const [{ data: t }, { data: j }] = await Promise.all([
      supabase.from('trades').select('*').eq('id', tradeId).single(),
      supabase.from('journals').select('*').eq('trade_id', tradeId).maybeSingle(),
    ])
    setTrade(t)
    setJournal(j)
    setLoading(false)
  }, [supabase, tradeId])

  useEffect(() => { load() }, [load])

  const handleCancel = async () => {
    if (!confirm('이 거래를 취소하시겠습니까? 보유 종목이 재계산됩니다.')) return
    setCancelling(true)
    await supabase.from('trades').update({ is_cancelled: true }).eq('id', tradeId)
    router.push('/records')
  }

  if (loading) {
    return (
      <div className="px-5 pt-6 space-y-4">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-20 w-full rounded-2xl" />
      </div>
    )
  }

  if (!trade) {
    return <div className="px-5 pt-16 text-center text-sm text-[#8B95A1]">거래를 찾을 수 없습니다</div>
  }

  const isBuy = trade.trade_type === 'buy'
  const totalAmount = trade.price * trade.quantity

  return (
    <div className="min-h-screen bg-white pb-8">
      {/* 헤더 */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-4">
        <button onClick={() => router.back()} className="w-8 h-8 flex items-center justify-center text-[#1A1A1A]">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-lg font-bold text-[#1A1A1A]">거래 상세</h1>
      </div>

      <div className="px-5 space-y-4">
        {/* 거래 요약 카드 */}
        <div className="bg-[#F7F8FA] rounded-3xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-lg font-bold text-[#1A1A1A]">{trade.name || trade.ticker}</p>
              <p className="text-sm text-[#8B95A1]">{trade.ticker} · {trade.market}</p>
            </div>
            <span className={clsx(
              'px-3 py-1.5 rounded-full text-xs font-bold text-white',
              isBuy ? 'bg-[#F04452]' : 'bg-[#1B6AC9]'
            )}>
              {isBuy ? '매수' : '매도'}
            </span>
          </div>

          <div className="space-y-2.5">
            {[
              { label: '거래일', value: formatDate(trade.traded_at) },
              { label: '수량', value: `${trade.quantity.toLocaleString()}주` },
              { label: '단가', value: formatKRW(trade.price) },
              { label: '수수료', value: formatKRW(trade.fee) },
              { label: '총 금액', value: formatKRW(totalAmount), bold: true },
            ].map(({ label, value, bold }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-sm text-[#8B95A1]">{label}</span>
                <span className={clsx('text-sm tabular', bold ? 'font-bold text-[#1A1A1A]' : 'text-[#1A1A1A]')}>
                  {value}
                </span>
              </div>
            ))}
          </div>

          {trade.memo && (
            <div className="mt-4 pt-4 border-t border-[#E5E8EB]">
              <p className="text-xs text-[#8B95A1] mb-1">메모</p>
              <p className="text-sm text-[#1A1A1A]">{trade.memo}</p>
            </div>
          )}
        </div>

        {/* 매매일지 */}
        {journal ? (
          <div className="bg-[#F7F8FA] rounded-3xl p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-bold text-[#1A1A1A]">매매일지</p>
              <div className="flex gap-2">
                {!journal.reflection && isBuy && (
                  <button
                    onClick={() => setShowReflectionSheet(true)}
                    className="text-xs text-[#3366FF] font-medium"
                  >
                    회고 추가
                  </button>
                )}
                <button
                  onClick={() => setShowJournalSheet(true)}
                  className="text-xs text-[#8B95A1]"
                >
                  수정
                </button>
              </div>
            </div>

            {journal.reason && (
              <div className="mb-3">
                <p className="text-xs text-[#8B95A1] mb-1">매수 이유</p>
                <p className="text-sm text-[#1A1A1A]">{journal.reason}</p>
              </div>
            )}

            <div className="flex gap-4 mb-3">
              {journal.target_price && (
                <div>
                  <p className="text-xs text-[#8B95A1]">목표가</p>
                  <p className="text-sm font-semibold text-[#F04452] tabular">{formatKRW(journal.target_price)}</p>
                </div>
              )}
              {journal.stop_loss_price && (
                <div>
                  <p className="text-xs text-[#8B95A1]">손절가</p>
                  <p className="text-sm font-semibold text-[#1B6AC9] tabular">{formatKRW(journal.stop_loss_price)}</p>
                </div>
              )}
            </div>

            {journal.reflection && (
              <div className="mb-3">
                <p className="text-xs text-[#8B95A1] mb-1">매도 후 회고</p>
                <p className="text-sm text-[#1A1A1A]">{journal.reflection}</p>
              </div>
            )}

            {journal.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {journal.tags.map(tag => (
                  <span key={tag} className="px-2.5 py-1 bg-[#F0F4FF] text-[#3366FF] rounded-full text-xs font-medium">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => setShowJournalSheet(true)}
            className="w-full flex items-center gap-3 py-4 px-5 border border-dashed border-[#E5E8EB] rounded-3xl"
          >
            <BookOpen size={20} className="text-[#3366FF]" />
            <span className="text-sm font-medium text-[#3366FF]">매매일지 작성하기</span>
          </button>
        )}

        {/* 거래 취소 */}
        {!trade.is_cancelled && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="w-full flex items-center justify-center gap-2 py-3.5 border border-[#F04452]/30 text-[#F04452] rounded-2xl text-sm font-medium disabled:opacity-50"
          >
            <XCircle size={16} />
            거래 취소 처리
          </button>
        )}
      </div>

      {/* 일지 작성/수정 바텀시트 */}
      <BottomSheet
        open={showJournalSheet}
        onClose={() => setShowJournalSheet(false)}
        title={journal ? '매매일지 수정' : '매매일지 작성'}
      >
        <JournalForm
          tradeId={tradeId}
          ticker={trade.ticker}
          journalId={journal?.id}
          onSaved={() => { setShowJournalSheet(false); load() }}
        />
      </BottomSheet>

      {/* 회고 작성 바텀시트 */}
      <BottomSheet
        open={showReflectionSheet}
        onClose={() => setShowReflectionSheet(false)}
        title="매도 후 회고"
      >
        <JournalForm
          tradeId={tradeId}
          ticker={trade.ticker}
          journalId={journal?.id}
          isReflection
          onSaved={() => { setShowReflectionSheet(false); load() }}
        />
      </BottomSheet>
    </div>
  )
}
