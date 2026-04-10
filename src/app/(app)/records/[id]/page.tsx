import { TradeDetail } from '@/components/records/TradeDetail'

export default async function TradeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <TradeDetail tradeId={id} />
}
