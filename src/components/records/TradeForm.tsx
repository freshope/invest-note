'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { createClient } from '@/lib/supabase/client'
import { formatNumberInput, parseNumberInput } from '@/lib/format'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { JournalForm } from './JournalForm'
import { ArrowLeft } from 'lucide-react'
import { clsx } from 'clsx'
import type { Account, TradeInsert } from '@/types/database'

const schema = z.object({
  accountId: z.string().min(1, '계좌를 선택하세요'),
  ticker: z.string().min(1, '종목 코드를 입력하세요').toUpperCase(),
  name: z.string().optional(),
  market: z.enum(['KR', 'US']),
  tradeType: z.enum(['buy', 'sell']),
  quantity: z.number().int().positive('수량은 1 이상이어야 합니다'),
  price: z.number().positive('가격을 입력하세요'),
  fee: z.number().min(0),
  tax: z.number().min(0),
  tradedAt: z.string().min(1, '날짜를 입력하세요'),
  memo: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

export function TradeForm() {
  const router = useRouter()
  const supabase = createClient()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(false)
  const [showJournalSheet, setShowJournalSheet] = useState(false)
  const [savedTradeId, setSavedTradeId] = useState<string | null>(null)
  const [priceInput, setPriceInput] = useState('')
  const [feeInput, setFeeInput] = useState('')
  const [taxInput, setTaxInput] = useState('')

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      market: 'KR',
      tradeType: 'buy',
      fee: 0,
      tax: 0,
      tradedAt: new Date().toISOString().split('T')[0],
    },
  })

  const tradeType = watch('tradeType')
  const market = watch('market')

  useEffect(() => {
    supabase.from('accounts').select('*').is('deleted_at', null).order('created_at').then(({ data }) => {
      if (data) setAccounts(data)
    })
  }, [supabase])

  const onSubmit = async (values: FormValues) => {
    setLoading(true)
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { setLoading(false); return }

    const trade: TradeInsert = {
      user_id: user.id,
      account_id: values.accountId,
      ticker: values.ticker,
      name: values.name || null,
      market: values.market,
      trade_type: values.tradeType,
      quantity: values.quantity,
      price: values.price,
      fee: values.fee,
      tax: values.tax,
      traded_at: values.tradedAt,
      memo: values.memo || null,
    }

    const { data, error } = await supabase.from('trades').insert(trade).select().single()

    if (!error && data && values.tradeType === 'buy') {
      setSavedTradeId(data.id)
      setShowJournalSheet(true)
    } else if (!error) {
      router.push('/records')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-white">
      {/* 헤더 */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-4">
        <button onClick={() => router.back()} className="w-8 h-8 flex items-center justify-center text-[#1A1A1A]">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-lg font-bold text-[#1A1A1A]">거래 기록</h1>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="px-5 space-y-4 pb-8">
        {/* 매수/매도 토글 */}
        <div className="flex bg-[#F7F8FA] rounded-2xl p-1">
          {(['buy', 'sell'] as const).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setValue('tradeType', type)}
              className={clsx(
                'flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all',
                tradeType === type
                  ? type === 'buy' ? 'bg-[#F04452] text-white' : 'bg-[#1B6AC9] text-white'
                  : 'text-[#8B95A1]'
              )}
            >
              {type === 'buy' ? '매수' : '매도'}
            </button>
          ))}
        </div>

        {/* 계좌 선택 */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">계좌</label>
          <select
            {...register('accountId')}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] outline-none focus:border-[#3366FF] bg-white"
          >
            <option value="">계좌 선택</option>
            {accounts.map(acc => (
              <option key={acc.id} value={acc.id}>{acc.name} ({acc.broker})</option>
            ))}
          </select>
          {errors.accountId && <p className="text-xs text-[#F04452] mt-1">{errors.accountId.message}</p>}
        </div>

        {/* 시장 선택 */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">시장</label>
          <div className="flex gap-2">
            {(['KR', 'US'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setValue('market', m)}
                className={clsx(
                  'px-4 py-2 rounded-xl text-sm font-medium border transition-all',
                  market === m ? 'border-[#3366FF] text-[#3366FF] bg-[#F0F4FF]' : 'border-[#E5E8EB] text-[#8B95A1]'
                )}
              >
                {m === 'KR' ? '🇰🇷 국내' : '🇺🇸 해외'}
              </button>
            ))}
          </div>
        </div>

        {/* 종목 코드 */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">
            종목 코드 {market === 'KR' ? '(6자리 숫자)' : '(티커, 예: AAPL)'}
          </label>
          <input
            {...register('ticker')}
            placeholder={market === 'KR' ? '005930' : 'AAPL'}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] font-mono"
          />
          {errors.ticker && <p className="text-xs text-[#F04452] mt-1">{errors.ticker.message}</p>}
        </div>

        {/* 종목명 (선택) */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">종목명 (선택)</label>
          <input
            {...register('name')}
            placeholder="삼성전자"
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
          />
        </div>

        {/* 수량 */}
        <div>
          <label htmlFor="trade-quantity" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">수량</label>
          <input
            id="trade-quantity"
            aria-label="수량"
            inputMode="numeric"
            placeholder="0"
            onChange={(e) => {
              const val = parseInt(e.target.value.replace(/[^0-9]/g, '')) || 0
              setValue('quantity', val)
            }}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] tabular"
          />
          {errors.quantity && <p className="text-xs text-[#F04452] mt-1">{errors.quantity.message}</p>}
        </div>

        {/* 단가 */}
        <div>
          <label htmlFor="trade-price" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">
            단가 {market === 'KR' ? '(원)' : '(달러)'}
          </label>
          <input
            id="trade-price"
            aria-label="단가"
            inputMode="decimal"
            value={priceInput}
            placeholder="0"
            onChange={(e) => {
              const formatted = formatNumberInput(e.target.value)
              setPriceInput(formatted)
              setValue('price', parseNumberInput(formatted))
            }}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] tabular"
          />
          {errors.price && <p className="text-xs text-[#F04452] mt-1">{errors.price.message}</p>}
        </div>

        {/* 수수료 */}
        <div>
          <label htmlFor="trade-fee" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">수수료 (선택)</label>
          <input
            id="trade-fee"
            aria-label="수수료"
            inputMode="decimal"
            value={feeInput}
            placeholder="0"
            onChange={(e) => {
              const formatted = formatNumberInput(e.target.value)
              setFeeInput(formatted)
              setValue('fee', parseNumberInput(formatted))
            }}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] tabular"
          />
        </div>

        {/* 제세금 */}
        <div>
          <label htmlFor="trade-tax" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">제세금 (선택)</label>
          <input
            id="trade-tax"
            aria-label="제세금"
            inputMode="decimal"
            value={taxInput}
            placeholder="0"
            onChange={(e) => {
              const formatted = formatNumberInput(e.target.value)
              setTaxInput(formatted)
              setValue('tax', parseNumberInput(formatted))
            }}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] tabular"
          />
        </div>

        {/* 날짜 */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">거래일</label>
          <input
            type="date"
            {...register('tradedAt')}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] outline-none focus:border-[#3366FF]"
          />
        </div>

        {/* 메모 */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">메모 (선택)</label>
          <textarea
            {...register('memo')}
            rows={3}
            placeholder="간단한 메모를 남겨보세요"
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] resize-none"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 bg-[#3366FF] text-white rounded-2xl text-sm font-bold disabled:opacity-50 mt-2"
        >
          {loading ? '저장 중...' : '기록 저장'}
        </button>
      </form>

      {/* 매수 후 일지 작성 바텀시트 */}
      {savedTradeId && (
        <BottomSheet
          open={showJournalSheet}
          onClose={() => { setShowJournalSheet(false); router.push('/records') }}
          title="매매일지 작성"
        >
          <p className="text-sm text-[#8B95A1] mb-4">매수 이유와 목표를 기록해 두세요.</p>
          <JournalForm
            tradeId={savedTradeId}
            onSaved={() => { setShowJournalSheet(false); router.push('/records') }}
            onSkip={() => { setShowJournalSheet(false); router.push('/records') }}
          />
        </BottomSheet>
      )}
    </div>
  )
}
