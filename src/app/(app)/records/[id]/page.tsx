import { TradeDetail } from '@/components/records/TradeDetail'

export default function TradeDetailPage({ params }: { params: { id: string } }) {
  return <TradeDetail tradeId={params.id} />
}
