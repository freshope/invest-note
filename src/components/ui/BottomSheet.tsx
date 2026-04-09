'use client'

import { useEffect } from 'react'
import { X } from 'lucide-react'

interface BottomSheetProps {
  open: boolean
  onClose: () => void
  title?: string
  children: React.ReactNode
}

export function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  // 열릴 때 스크롤 잠금
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <>
      <div className="sheet-overlay" onClick={onClose} />
      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] bg-white rounded-t-3xl z-50 max-h-[90vh] flex flex-col"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 16px)' }}
      >
        {/* 핸들 */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 bg-[#E5E8EB] rounded-full" />
        </div>

        {/* 헤더 */}
        {title && (
          <div className="flex items-center justify-between px-5 py-3">
            <h2 className="text-lg font-bold text-[#1A1A1A]">{title}</h2>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center text-[#8B95A1]">
              <X size={20} />
            </button>
          </div>
        )}

        {/* 컨텐츠 */}
        <div className="flex-1 overflow-y-auto px-5 py-2">
          {children}
        </div>
      </div>
    </>
  )
}
