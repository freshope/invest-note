import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function GET(request: NextRequest) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const q = searchParams.get('q')?.trim()
  const market = searchParams.get('market') || 'KR'

  if (!['KR', 'US'].includes(market)) return NextResponse.json([], { status: 400 })
  if (!q || q.length < 2 || q.length > 100) return NextResponse.json([])

  if (market === 'KR') {
    try {
      const url = `https://ac.stock.naver.com/ac?q=${encodeURIComponent(q)}&target=stock`
      const res = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        next: { revalidate: 300 },
      })
      if (!res.ok) return NextResponse.json([])
      const data = await res.json()
      // 네이버 응답: { items: [{code, name, typeCode, ...}, ...], query: "..." }
      const items: { code: string; name: string }[] = Array.isArray(data.items) ? data.items : []
      const results = items.slice(0, 8).map(({ code, name }) => ({ ticker: code, name }))
      return NextResponse.json(results)
    } catch {
      return NextResponse.json([])
    }
  }

  // US 시장은 미지원 (graceful empty)
  return NextResponse.json([])
}
