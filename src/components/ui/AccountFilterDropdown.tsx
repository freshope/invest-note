'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { clsx } from 'clsx'
import type { Account } from '@/types/database'

interface AccountFilterDropdownProps {
  accounts: Account[]
  selectedAccountId: string
  onSelect: (id: string) => void
}

export function AccountFilterDropdown({ accounts, selectedAccountId, onSelect }: AccountFilterDropdownProps) {
  const [open, setOpen] = useState(false)

  const selectedName = selectedAccountId === 'all'
    ? '전체 계좌'
    : accounts.find(a => a.id === selectedAccountId)?.name || '전체 계좌'

  const items = [{ id: 'all', name: '전체 계좌' }, ...accounts.map(a => ({ id: a.id, name: a.name }))]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-sm font-medium text-[#1A1A1A] min-h-[44px]"
      >
        {selectedName}
        <ChevronDown size={14} className={clsx('transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 min-w-[160px] bg-white border border-[#E5E8EB] rounded-2xl shadow-lg overflow-hidden z-50">
          {items.map(item => (
            <button
              key={item.id}
              onClick={() => { onSelect(item.id); setOpen(false) }}
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
    </div>
  )
}
