export type TradeType = 'buy' | 'sell'
export type MarketType = 'KR' | 'US'

export interface Database {
  public: {
    Tables: {
      accounts: {
        Row: {
          id: string
          user_id: string
          name: string
          broker: string
          account_number: string | null
          is_active: boolean
          created_at: string
          updated_at: string
          fee_rate: number
          deleted_at: string | null
          cash_balance: number
          cash_balance_updated_at: string | null
        }
        Insert: {
          id?: string
          user_id: string
          name: string
          broker: string
          account_number?: string | null
          fee_rate?: number
          is_active?: boolean
          created_at?: string
          updated_at?: string
          deleted_at?: string | null
          cash_balance?: number
          cash_balance_updated_at?: string | null
        }
        Update: {
          id?: string
          user_id?: string
          name?: string
          broker?: string
          account_number?: string | null
          fee_rate?: number
          is_active?: boolean
          updated_at?: string
          deleted_at?: string | null
          cash_balance?: number
          cash_balance_updated_at?: string | null
        }
      }
      trades: {
        Row: {
          id: string
          user_id: string
          account_id: string
          ticker: string
          name: string | null
          market: MarketType
          trade_type: TradeType
          quantity: number
          price: number
          fee: number
          tax: number
          traded_at: string
          memo: string | null
          is_cancelled: boolean
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          account_id: string
          ticker: string
          name?: string | null
          market: MarketType
          trade_type: TradeType
          quantity: number
          price: number
          fee?: number
          tax?: number
          traded_at: string
          memo?: string | null
          is_cancelled?: boolean
          created_at?: string
        }
        Update: {
          ticker?: string
          name?: string | null
          market?: MarketType
          trade_type?: TradeType
          quantity?: number
          price?: number
          fee?: number
          tax?: number
          traded_at?: string
          memo?: string | null
          is_cancelled?: boolean
        }
      }
      journals: {
        Row: {
          id: string
          user_id: string
          trade_id: string | null
          ticker: string
          name: string | null
          market: MarketType
          reason: string | null
          target_price: number | null
          stop_loss_price: number | null
          reflection: string | null
          tags: string[]
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          trade_id?: string | null
          ticker: string
          name?: string | null
          market: MarketType
          reason?: string | null
          target_price?: number | null
          stop_loss_price?: number | null
          reflection?: string | null
          tags?: string[]
          created_at?: string
          updated_at?: string
        }
        Update: {
          reason?: string | null
          target_price?: number | null
          stop_loss_price?: number | null
          reflection?: string | null
          tags?: string[]
          updated_at?: string
        }
      }
      holdings: {
        Row: {
          id: string
          user_id: string
          account_id: string
          ticker: string
          name: string | null
          market: MarketType
          quantity: number
          avg_price: number
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          account_id: string
          ticker: string
          name?: string | null
          market: MarketType
          quantity: number
          avg_price: number
          updated_at?: string
        }
        Update: {
          quantity?: number
          avg_price?: number
          name?: string | null
          updated_at?: string
        }
      }
    }
    Views: Record<string, never>
    Functions: Record<string, never>
    Enums: {
      trade_type: TradeType
      market_type: MarketType
    }
  }
}

// 편의 타입
export type Account = Database['public']['Tables']['accounts']['Row']
export type Trade = Database['public']['Tables']['trades']['Row']
export type Journal = Database['public']['Tables']['journals']['Row']
export type Holding = Database['public']['Tables']['holdings']['Row']

export type AccountInsert = Database['public']['Tables']['accounts']['Insert']
export type TradeInsert = Database['public']['Tables']['trades']['Insert']
export type JournalInsert = Database['public']['Tables']['journals']['Insert']
