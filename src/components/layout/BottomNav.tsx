'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, BookOpen, PieChart, Settings } from 'lucide-react'
import { clsx } from 'clsx'

const tabs = [
  { href: '/', icon: Home, label: '홈' },
  { href: '/records', icon: BookOpen, label: '기록' },
  { href: '/assets', icon: PieChart, label: '자산' },
  { href: '/settings', icon: Settings, label: '설정' },
]

export function BottomNav() {
  const pathname = usePathname()

  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] bg-white border-t border-[#E5E8EB] z-40"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
      <div className="flex">
        {tabs.map(({ href, icon: Icon, label }) => {
          const isActive = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex-1 flex flex-col items-center justify-center py-3 gap-1 min-h-[64px]',
                isActive ? 'text-[#3366FF]' : 'text-[#8B95A1]'
              )}
            >
              <Icon size={22} strokeWidth={isActive ? 2.5 : 1.8} />
              <span className={clsx('text-[11px]', isActive ? 'font-semibold' : 'font-normal')}>
                {label}
              </span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
