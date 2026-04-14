'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { createClient } from '@/lib/supabase/client'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { ArrowLeft, Plus, Trash2, LogOut, Pencil } from 'lucide-react'
import { clsx } from 'clsx'
import type { Account, AccountInsert } from '@/types/database'
import { DEFAULT_FEE_RATE } from '@/lib/constants'

const accountSchema = z.object({
  name: z.string().min(1, '계좌명을 입력하세요'),
  broker: z.string().min(1, '증권사를 선택하세요'),
  accountNumber: z.string().optional(),
  feeRate: z.number().min(0).max(9.9999),
  cashBalance: z.number().min(0, '예수금은 0 이상이어야 합니다'),
})

type AccountForm = z.infer<typeof accountSchema>

const BROKERS = [
  '키움증권', '삼성증권', 'NH투자증권', 'KB증권',
  '미래에셋증권', '한국투자증권', '신한투자증권',
  '토스증권', 'IBK투자증권', '대신증권', '기타',
]

const BROKER_COLORS: Record<string, string> = {
  '키움증권': '#E8003D',
  '삼성증권': '#1259AA',
  'NH투자증권': '#009D6E',
  'KB증권': '#FFBC00',
  '미래에셋증권': '#E4003A',
  '한국투자증권': '#FF6B00',
  '신한투자증권': '#0046FF',
  '토스증권': '#1B64DA',
  'IBK투자증권': '#004EA2',
  '대신증권': '#003087',
  '기타': '#8B95A1',
}

// 밝은 배경색(KB증권 노랑 등)에서 가독성을 위해 어두운 텍스트 사용
const LIGHT_BROKERS = new Set(['KB증권'])

function BrokerBadge({ broker, size = 'sm' }: { broker: string; size?: 'sm' | 'lg' }) {
  const color = BROKER_COLORS[broker] || '#8B95A1'
  const initial = broker.charAt(0)
  const dim = size === 'lg' ? 'w-9 h-9 text-base' : 'w-7 h-7 text-xs'
  const textColor = LIGHT_BROKERS.has(broker) ? '#1A1A1A' : '#FFFFFF'
  return (
    <span
      className={clsx('rounded-full flex items-center justify-center font-bold flex-shrink-0', dim)}
      style={{ backgroundColor: color, color: textColor }}
    >
      {initial}
    </span>
  )
}

function BrokerPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {BROKERS.map(broker => (
        <button
          key={broker}
          type="button"
          onClick={() => onChange(broker)}
          className={clsx(
            'flex items-center gap-2.5 px-3 py-2.5 rounded-2xl border text-sm font-medium transition-all text-left',
            value === broker
              ? 'border-[#3366FF] bg-[#F0F4FF] text-[#3366FF]'
              : 'border-[#E5E8EB] text-[#1A1A1A]'
          )}
        >
          <BrokerBadge broker={broker} />
          <span className="truncate">{broker}</span>
        </button>
      ))}
    </div>
  )
}

export function SettingsView() {
  const router = useRouter()
  const supabase = createClient()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [showAddSheet, setShowAddSheet] = useState(false)
  const [showEditSheet, setShowEditSheet] = useState(false)
  const [editingAccount, setEditingAccount] = useState<Account | null>(null)
  const [saving, setSaving] = useState(false)
  const [selectedBroker, setSelectedBroker] = useState('')
  const [editBroker, setEditBroker] = useState('')

  const addForm = useForm<AccountForm>({
    resolver: zodResolver(accountSchema),
    defaultValues: { feeRate: DEFAULT_FEE_RATE, cashBalance: 0 },
  })

  const editForm = useForm<AccountForm>({
    resolver: zodResolver(accountSchema),
  })

  const load = useCallback(async () => {
    const { data } = await supabase.from('accounts').select('*').is('deleted_at', null).order('created_at')
    setAccounts(data || [])
  }, [supabase])

  useEffect(() => { load() }, [load])

  const onAddAccount = async (values: AccountForm) => {
    setSaving(true)
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) { setSaving(false); return }

    const cashBalance = values.cashBalance ?? 0
    const account: AccountInsert = {
      user_id: user.id,
      name: values.name,
      broker: values.broker,
      account_number: values.accountNumber || null,
      fee_rate: values.feeRate,
      cash_balance: cashBalance,
      cash_balance_updated_at: cashBalance > 0 ? new Date().toISOString() : null,
    }

    const { error } = await supabase.from('accounts').insert(account)
    if (error) {
      alert('계좌 추가 중 오류가 발생했습니다. 다시 시도해주세요.')
      setSaving(false)
      return
    }
    addForm.reset({ feeRate: DEFAULT_FEE_RATE, cashBalance: 0 })
    setSelectedBroker('')
    setShowAddSheet(false)
    setSaving(false)
    load()
  }

  const onEditAccount = async (values: AccountForm) => {
    if (!editingAccount) return
    setSaving(true)
    const now = new Date().toISOString()
    const { error } = await supabase.from('accounts').update({
      name: values.name,
      broker: values.broker,
      account_number: values.accountNumber || null,
      fee_rate: values.feeRate,
      cash_balance: values.cashBalance ?? 0,
      // 예수금이 실제로 변경된 경우에만 타임스탬프 갱신 (staleness 정확도 유지)
      cash_balance_updated_at: (values.cashBalance ?? 0) !== (editingAccount.cash_balance ?? 0) ? now : editingAccount.cash_balance_updated_at,
      updated_at: now,
    }).eq('id', editingAccount.id)
    if (error) {
      alert('계좌 수정 중 오류가 발생했습니다. 다시 시도해주세요.')
      setSaving(false)
      return
    }
    setShowEditSheet(false)
    setEditingAccount(null)
    setSaving(false)
    load()
  }

  const openEdit = (acc: Account) => {
    setEditingAccount(acc)
    setEditBroker(acc.broker)
    editForm.reset({
      name: acc.name,
      broker: acc.broker,
      accountNumber: acc.account_number || '',
      feeRate: acc.fee_rate ?? DEFAULT_FEE_RATE,
      cashBalance: acc.cash_balance ?? 0,
    })
    setShowEditSheet(true)
  }

  const deleteAccount = async (id: string) => {
    if (!confirm('계좌를 삭제하시겠습니까?\n계좌의 거래 내역은 보존됩니다.')) return
    const { error } = await supabase.from('accounts').update({ deleted_at: new Date().toISOString() }).eq('id', id)
    if (error) { alert('계좌 삭제 중 오류가 발생했습니다. 다시 시도해주세요.'); return }
    load()
  }

  const signOut = async () => {
    await supabase.auth.signOut()
    router.push('/auth/login')
  }

  return (
    <div className="min-h-screen bg-white pb-8">
      {/* 헤더 */}
      <div className="flex items-center gap-3 px-5 pt-6 pb-4">
        <button onClick={() => router.back()} className="w-11 h-11 flex items-center justify-center text-[#1A1A1A]">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-lg font-bold text-[#1A1A1A]">설정</h1>
      </div>

      <div className="px-5 space-y-6">
        {/* 계좌 관리 */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-[#1A1A1A]">계좌 관리</h2>
            <button
              onClick={() => setShowAddSheet(true)}
              className="flex items-center gap-1 text-xs text-[#3366FF] font-medium"
            >
              <Plus size={14} />
              계좌 추가
            </button>
          </div>

          {accounts.length === 0 ? (
            <div className="py-6 text-center border border-dashed border-[#E5E8EB] rounded-2xl">
              <p className="text-sm text-[#8B95A1] mb-3">등록된 계좌가 없습니다</p>
              <button
                onClick={() => setShowAddSheet(true)}
                className="text-sm text-[#3366FF] font-medium"
              >
                계좌 추가하기
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {accounts.map(acc => (
                <div key={acc.id} className="flex items-center justify-between py-3 px-4 bg-[#F7F8FA] rounded-2xl">
                  <div className="flex items-center gap-3 min-w-0">
                    <BrokerBadge broker={acc.broker} />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[#1A1A1A] truncate">{acc.name}</p>
                      <p className="text-xs text-[#8B95A1]">
                        {acc.broker}
                        {acc.account_number ? ` · ${acc.account_number}` : ''}
                        {` · 수수료 ${acc.fee_rate ?? DEFAULT_FEE_RATE}%`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => openEdit(acc)}
                      className="w-11 h-11 flex items-center justify-center text-[#8B95A1]"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      onClick={() => deleteAccount(acc.id)}
                      className="w-11 h-11 flex items-center justify-center text-[#8B95A1]"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 로그아웃 */}
        <section>
          <button
            onClick={signOut}
            className="w-full flex items-center gap-3 py-3.5 px-4 border border-[#E5E8EB] rounded-2xl text-sm text-[#8B95A1]"
          >
            <LogOut size={18} />
            로그아웃
          </button>
        </section>
      </div>

      {/* 계좌 추가 바텀시트 */}
      <BottomSheet
        open={showAddSheet}
        onClose={() => { setShowAddSheet(false); addForm.reset({ feeRate: DEFAULT_FEE_RATE }); setSelectedBroker('') }}
        title="계좌 추가"
        footer={
          <button
            form="add-account-form"
            type="submit"
            disabled={saving}
            className="w-full py-4 bg-[#3366FF] text-white rounded-2xl text-sm font-bold disabled:opacity-50"
          >
            {saving ? '저장 중...' : '계좌 추가'}
          </button>
        }
      >
        <form id="add-account-form" onSubmit={addForm.handleSubmit(onAddAccount)} className="space-y-4 pb-2">
          <AccountFormFields
            form={addForm}
            brokerValue={selectedBroker}
            onBrokerChange={(v) => { setSelectedBroker(v); addForm.setValue('broker', v) }}
          />
        </form>
      </BottomSheet>

      {/* 계좌 편집 바텀시트 */}
      <BottomSheet
        open={showEditSheet}
        onClose={() => { setShowEditSheet(false); setEditingAccount(null); setEditBroker('') }}
        title="계좌 편집"
        footer={
          <button
            form="edit-account-form"
            type="submit"
            disabled={saving}
            className="w-full py-4 bg-[#3366FF] text-white rounded-2xl text-sm font-bold disabled:opacity-50"
          >
            {saving ? '저장 중...' : '저장'}
          </button>
        }
      >
        <form id="edit-account-form" onSubmit={editForm.handleSubmit(onEditAccount)} className="space-y-4 pb-2">
          <AccountFormFields
            form={editForm}
            brokerValue={editBroker}
            onBrokerChange={(v) => { setEditBroker(v); editForm.setValue('broker', v) }}
          />
        </form>
      </BottomSheet>
    </div>
  )
}

function AccountFormFields({
  form,
  brokerValue,
  onBrokerChange,
}: {
  form: UseFormReturn<AccountForm>
  brokerValue: string
  onBrokerChange: (v: string) => void
}) {
  const { register, formState: { errors } } = form
  return (
    <>
      <div>
        <label htmlFor="account-name" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">계좌명</label>
        <input
          id="account-name"
          {...register('name')}
          placeholder="예: 주식 투자 계좌"
          className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
        />
        {errors.name && <p className="text-xs text-[#F04452] mt-1">{errors.name.message}</p>}
      </div>

      <div>
        <label className="text-xs font-medium text-[#8B95A1] mb-2 block">증권사</label>
        <BrokerPicker value={brokerValue} onChange={onBrokerChange} />
        {errors.broker && <p className="text-xs text-[#F04452] mt-1">{errors.broker.message}</p>}
      </div>

      <div>
        <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">계좌번호 (선택)</label>
        <input
          {...register('accountNumber')}
          placeholder="123-456789-01"
          className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
        />
      </div>

      <div>
        <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">수수료율 (%)</label>
        <input
          inputMode="decimal"
          {...register('feeRate', { valueAsNumber: true })}
          placeholder="0.015"
          className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
        />
        <p className="text-xs text-[#8B95A1] mt-1">예: 0.015 (키움증권 기본값)</p>
        {errors.feeRate && <p className="text-xs text-[#F04452] mt-1">{errors.feeRate.message}</p>}
      </div>

      <div>
        <label className="text-xs font-medium text-[#8B95A1] mb-1.5 block">예수금 (직접 입력)</label>
        <input
          inputMode="decimal"
          {...register('cashBalance', { valueAsNumber: true })}
          placeholder="0"
          className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] placeholder-[#8B95A1] outline-none focus:border-[#3366FF]"
        />
        <p className="text-xs text-[#8B95A1] mt-1">증권사 앱에서 확인한 예수금 (미입력 시 0)</p>
        {errors.cashBalance && <p className="text-xs text-[#F04452] mt-1">{errors.cashBalance.message}</p>}
      </div>
    </>
  )
}
