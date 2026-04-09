'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { createClient } from '@/lib/supabase/client'
import { formatNumberInput, parseNumberInput } from '@/lib/format'
import { X } from 'lucide-react'

const PRESET_TAGS = ['성장주', '가치주', '배당', '단기', '중장기', '모멘텀', '반등', '테마']

const schema = z.object({
  reason: z.string().optional(),
  targetPrice: z.number().optional(),
  stopLossPrice: z.number().optional(),
  reflection: z.string().optional(),
  tags: z.array(z.string()),
})

type FormValues = z.infer<typeof schema>

interface JournalFormProps {
  tradeId: string
  ticker?: string
  isReflection?: boolean  // 2단계 (매도 후 회고) 모드
  journalId?: string      // 기존 일지 수정 시
  onSaved: () => void
  onSkip?: () => void
}

export function JournalForm({ tradeId, ticker, isReflection = false, journalId, onSaved, onSkip }: JournalFormProps) {
  const supabase = createClient()
  const [loading, setLoading] = useState(false)
  const [targetInput, setTargetInput] = useState('')
  const [stopLossInput, setStopLossInput] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [customTag, setCustomTag] = useState('')

  const { register, handleSubmit, setValue } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { tags: [] },
  })

  const toggleTag = (tag: string) => {
    setSelectedTags(prev => {
      const next = prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
      setValue('tags', next)
      return next
    })
  }

  const addCustomTag = () => {
    if (customTag.trim() && !selectedTags.includes(customTag.trim())) {
      const next = [...selectedTags, customTag.trim()]
      setSelectedTags(next)
      setValue('tags', next)
      setCustomTag('')
    }
  }

  const onSubmit = async (values: FormValues) => {
    setLoading(true)
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    const payload = {
      user_id: user.id,
      trade_id: tradeId,
      ticker: ticker || '',
      reason: values.reason || null,
      target_price: values.targetPrice || null,
      stop_loss_price: values.stopLossPrice || null,
      reflection: values.reflection || null,
      tags: selectedTags,
    }

    if (journalId) {
      await supabase.from('journals').update(payload).eq('id', journalId)
    } else {
      await supabase.from('journals').insert({ ...payload, market: 'KR' })
    }

    setLoading(false)
    onSaved()
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pb-4">
      {!isReflection && (
        <>
          {/* 매수 이유 */}
          <div>
            <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">매수 이유</label>
            <textarea
              {...register('reason')}
              rows={4}
              placeholder="왜 이 종목을 매수했나요? 어떤 분석을 했나요?"
              className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] resize-none"
            />
          </div>

          {/* 목표가 */}
          <div>
            <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">목표가</label>
            <input
              inputMode="decimal"
              value={targetInput}
              placeholder="0"
              onChange={(e) => {
                const f = formatNumberInput(e.target.value)
                setTargetInput(f)
                setValue('targetPrice', parseNumberInput(f))
              }}
              className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] tabular"
            />
          </div>

          {/* 손절가 */}
          <div>
            <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">손절가</label>
            <input
              inputMode="decimal"
              value={stopLossInput}
              placeholder="0"
              onChange={(e) => {
                const f = formatNumberInput(e.target.value)
                setStopLossInput(f)
                setValue('stopLossPrice', parseNumberInput(f))
              }}
              className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] tabular"
            />
          </div>
        </>
      )}

      {isReflection && (
        <div>
          <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">매도 후 회고</label>
          <textarea
            {...register('reflection')}
            rows={5}
            placeholder="이번 매매에서 배운 점은 무엇인가요? 다음엔 어떻게 달라지고 싶으신가요?"
            className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF] resize-none"
          />
        </div>
      )}

      {/* 태그 */}
      <div>
        <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">태그</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {PRESET_TAGS.map(tag => (
            <button
              key={tag}
              type="button"
              onClick={() => toggleTag(tag)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                selectedTags.includes(tag)
                  ? 'bg-[#3366FF] text-white border-[#3366FF]'
                  : 'border-[#E5E8EB] text-[#8B95A1]'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
        {/* 커스텀 태그 */}
        <div className="flex gap-2">
          <input
            value={customTag}
            onChange={(e) => setCustomTag(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomTag() } }}
            placeholder="직접 입력"
            className="flex-1 px-4 py-2.5 border border-[#E5E8EB] rounded-xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
          />
          <button
            type="button"
            onClick={addCustomTag}
            className="px-4 py-2.5 bg-[#F7F8FA] rounded-xl text-sm text-[#3366FF] font-medium"
          >
            추가
          </button>
        </div>
        {/* 선택된 커스텀 태그 표시 */}
        {selectedTags.filter(t => !PRESET_TAGS.includes(t)).length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {selectedTags.filter(t => !PRESET_TAGS.includes(t)).map(tag => (
              <span key={tag} className="flex items-center gap-1 px-3 py-1.5 bg-[#F0F4FF] text-[#3366FF] rounded-full text-xs font-medium">
                {tag}
                <button type="button" onClick={() => toggleTag(tag)}>
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex gap-3">
        {onSkip && (
          <button
            type="button"
            onClick={onSkip}
            className="flex-1 py-3.5 border border-[#E5E8EB] text-[#8B95A1] rounded-2xl text-sm font-semibold"
          >
            나중에
          </button>
        )}
        <button
          type="submit"
          disabled={loading}
          className="flex-1 py-3.5 bg-[#3366FF] text-white rounded-2xl text-sm font-bold disabled:opacity-50"
        >
          {loading ? '저장 중...' : '저장'}
        </button>
      </div>
    </form>
  )
}
