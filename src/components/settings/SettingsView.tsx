'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { createClient } from '@/lib/supabase/client'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { ArrowLeft, Plus, Trash2, LogOut } from 'lucide-react'
import type { Account, AccountInsert } from '@/types/database'

const accountSchema = z.object({
  name: z.string().min(1, '계좌명을 입력하세요'),
  broker: z.string().min(1, '증권사를 입력하세요'),
  accountNumber: z.string().optional(),
})

type AccountForm = z.infer<typeof accountSchema>

const BROKERS = ['키움증권', '삼성증권', 'NH투자증권', 'KB증권', '미래에셋증권', '한국투자증권', '신한투자증권', 'IBK투자증권', '대신증권', '기타']

export function SettingsView() {
  const router = useRouter()
  const supabase = createClient()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [showAddSheet, setShowAddSheet] = useState(false)
  const [saving, setSaving] = useState(false)

  const { register, handleSubmit, reset, formState: { errors } } = useForm<AccountForm>({
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
    if (!user) return

    const account: AccountInsert = {
      user_id: user.id,
      name: values.name,
      broker: values.broker,
      account_number: values.accountNumber || null,
    }

    await supabase.from('accounts').insert(account)
    reset()
    setShowAddSheet(false)
    setSaving(false)
    load()
  }

  const deleteAccount = async (id: string) => {
    if (!confirm('계좌를 삭제하시겠습니까?\n계좌의 거래 내역은 보존됩니다.')) return
    await supabase.from('accounts').update({ deleted_at: new Date().toISOString() }).eq('id', id)
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
        <button onClick={() => router.back()} className="w-8 h-8 flex items-center justify-center text-[#1A1A1A]">
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
                  <div>
                    <p className="text-sm font-semibold text-[#1A1A1A]">{acc.name}</p>
                    <p className="text-xs text-[#8B95A1]">{acc.broker}{acc.account_number ? ` · ${acc.account_number}` : ''}</p>
                  </div>
                  <button
                    onClick={() => deleteAccount(acc.id)}
                    className="w-8 h-8 flex items-center justify-center text-[#8B95A1]"
                  >
                    <Trash2 size={16} />
                  </button>
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
      <BottomSheet open={showAddSheet} onClose={() => setShowAddSheet(false)} title="계좌 추가">
        <form onSubmit={handleSubmit(onAddAccount)} className="space-y-4 pb-4">
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
            <label htmlFor="account-broker" className="text-xs font-medium text-[#8B95A1] mb-1.5 block">증권사</label>
            <select
              id="account-broker"
              {...register('broker')}
              className="w-full px-4 py-3.5 border border-[#E5E8EB] rounded-2xl text-sm text-[#1A1A1A] outline-none focus:border-[#3366FF] bg-white"
            >
              <option value="">증권사 선택</option>
              {BROKERS.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
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

          <button
            type="submit"
            disabled={saving}
            className="w-full py-4 bg-[#3366FF] text-white rounded-2xl text-sm font-bold disabled:opacity-50"
          >
            {saving ? '저장 중...' : '계좌 추가'}
          </button>
        </form>
      </BottomSheet>
    </div>
  )
}
