'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
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
import { DEFAULT_FEE_RATE, KR_SELL_TAX_RATE } from '@/lib/constants'

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
type SearchResult = { ticker: string; name: string }

export function TradeForm() {
  const router = useRouter()
  const supabase = createClient()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(false)
  const [showJournalSheet, setShowJournalSheet] = useState(false)
  const [savedTradeId, setSavedTradeId] = useState<string | null>(null)
  const [quantityInput, setQuantityInput] = useState('')
  const [priceInput, setPriceInput] = useState('')
  const [feeInput, setFeeInput] = useState('')
  const [taxInput, setTaxInput] = useState('')

  // 종목 검색 상태
  const [nameInput, setNameInput] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)

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
  const accountId = watch('accountId')
  const quantity = watch('quantity')
  const price = watch('price')

  useEffect(() => {
    supabase.from('accounts').select('*').is('deleted_at', null).order('created_at').then(({ data }) => {
      if (data) setAccounts(data)
    })
  }, [supabase])

  // 검색 디바운스 타이머 정리
  useEffect(() => {
    return () => {
      if (searchDebounce.current) clearTimeout(searchDebounce.current)
    }
  }, [])

  // 수수료/세금 자동계산
  useEffect(() => {
    const selectedAccount = accounts.find(a => a.id === accountId)
    if (!selectedAccount || !quantity || !price || quantity <= 0 || price <= 0) return

    const totalAmount = quantity * price
    const feeRate = selectedAccount.fee_rate ?? DEFAULT_FEE_RATE

    // 수수료: 총액 × fee_rate(%)
    const feeAmt = Math.round(totalAmount * feeRate / 100)
    setValue('fee', feeAmt)
    setFeeInput(feeAmt > 0 ? formatNumberInput(String(feeAmt)) : '')

    // 제세금: KR 매도만 0.18%, 나머지 0
    if (market === 'KR' && tradeType === 'sell') {
      const taxAmt = Math.round(totalAmount * KR_SELL_TAX_RATE)
      setValue('tax', taxAmt)
      setTaxInput(taxAmt > 0 ? formatNumberInput(String(taxAmt)) : '')
    } else {
      setValue('tax', 0)
      setTaxInput('')
    }
  }, [accountId, quantity, price, tradeType, market, accounts, setValue])

  // 종목 검색
  const searchStocks = useCallback(async (q: string, mkt: string) => {
    if (q.length < 2 || mkt !== 'KR') {
      setSearchResults([])
      setShowDropdown(false)
      return
    }
    setSearching(true)
    try {
      const res = await fetch(`/api/stock-search?q=${encodeURIComponent(q)}&market=${mkt}`)
      if (res.ok) {
        const data: SearchResult[] = await res.json()
        setSearchResults(data)
        setShowDropdown(data.length > 0)
      }
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }, [])

  const handleNameChange = (value: string) => {
    setNameInput(value)
    setValue('name', value)
    if (searchDebounce.current) clearTimeout(searchDebounce.current)
    if (value.length >= 2) {
      searchDebounce.current = setTimeout(() => searchStocks(value, market), 300)
    } else {
      setSearchResults([])
      setShowDropdown(false)
    }
  }

  const selectStock = (result: SearchResult) => {
    setNameInput(result.name)
    setValue('name', result.name)
    setValue('ticker', result.ticker)
    setShowDropdown(false)
    setSearchResults([])
    setTimeout(() => nameInputRef.current?.focus(), 0)
  }

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
                onClick={() => { setValue('market', m); setShowDropdown(false) }}
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

        {/* 날짜 */}
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">거래일</label>
          <input
            type="date"
            {...register('tradedAt')}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] outline-none focus:border-[#3366FF]"
          />
        </div>

        {/* 종목명 (검색) */}
        <div className="relative" ref={dropdownRef}>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">
            종목명 {market === 'KR' ? '(검색)' : '(선택)'}
          </label>
          <input
            ref={nameInputRef}
            value={nameInput}
            onChange={(e) => handleNameChange(e.target.value)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
            placeholder={market === 'KR' ? '삼성전자 검색...' : '예: Apple'}
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
          />
          {/* 자동완성 드롭다운 */}
          {showDropdown && (
            <div className="absolute z-10 left-0 right-0 top-full mt-1 bg-white border border-[#E5E8EB] rounded-2xl shadow-lg overflow-hidden">
              {searching ? (
                <div className="px-4 py-3 text-sm text-[#8B95A1]">검색 중...</div>
              ) : searchResults.length === 0 ? (
                <div className="px-4 py-3 text-sm text-[#8B95A1]">검색 결과 없음</div>
              ) : (
                searchResults.map((r) => (
                  <button
                    key={r.ticker}
                    type="button"
                    onMouseDown={() => selectStock(r)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-[#F7F8FA] text-left transition-colors"
                  >
                    <span className="text-sm text-[#1A1A1A] font-medium">{r.name}</span>
                    <span className="text-xs text-[#8B95A1] font-mono">{r.ticker}</span>
                  </button>
                ))
              )}
            </div>
          )}
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

        {/* 수량 */}
        <div>
          <label htmlFor="trade-quantity" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">수량</label>
          <input
            id="trade-quantity"
            aria-label="수량"
            inputMode="numeric"
            value={quantityInput}
            placeholder="0"
            onChange={(e) => {
              const formatted = formatNumberInput(e.target.value)
              setQuantityInput(formatted)
              setValue('quantity', Math.round(parseNumberInput(formatted)))
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
          <label htmlFor="trade-fee" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">
            수수료 (선택)
            {accountId && accounts.find(a => a.id === accountId) && (
              <span className="ml-1 text-[#3366FF]">· 자동계산됨</span>
            )}
          </label>
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
          <label htmlFor="trade-tax" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">
            제세금 (선택)
            {market === 'KR' && tradeType === 'sell' && accountId && (
              <span className="ml-1 text-[#3366FF]">· 자동계산됨 (0.18%)</span>
            )}
          </label>
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
