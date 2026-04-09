import { describe, it, expect } from 'vitest'
import { formatKRW, formatPnL, formatNumberInput, parseNumberInput } from '@/lib/format'

describe('formatKRW', () => {
  it('formats positive numbers with ₩ prefix', () => {
    expect(formatKRW(1000000)).toBe('₩1,000,000')
  })

  it('formats zero', () => {
    expect(formatKRW(0)).toBe('₩0')
  })
})

describe('formatPnL', () => {
  it('returns red color for profit', () => {
    const result = formatPnL(10000, 5)
    expect(result.colorClass).toContain('F04452')
  })

  it('returns blue color for loss', () => {
    const result = formatPnL(-5000, -2.5)
    expect(result.colorClass).toContain('1B6AC9')
  })

  it('returns neutral color for zero', () => {
    const result = formatPnL(0, 0)
    expect(result.colorClass).toBe('text-[#8B95A1]')
  })
})

describe('formatNumberInput / parseNumberInput', () => {
  it('formats number with commas', () => {
    expect(formatNumberInput('1000000')).toBe('1,000,000')
  })

  it('parses formatted number back to float', () => {
    expect(parseNumberInput('1,000,000')).toBe(1000000)
  })

  it('handles decimal numbers', () => {
    expect(formatNumberInput('1234.56')).toBe('1,234.56')
    expect(parseNumberInput('1,234.56')).toBe(1234.56)
  })
})
