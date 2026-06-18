--
-- PostgreSQL database dump
--

\restrict 2CPTJf3HOZ7mbgh6OXlTmMy18a7rSnVJiMzAif6ni8hMFAOuu8rYfHL1vcrrS3c

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: emotion_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.emotion_type AS ENUM (
    'CONFIDENT',
    'ANXIOUS',
    'FOMO',
    'IMPULSIVE',
    'CALM'
);


ALTER TYPE public.emotion_type OWNER TO postgres;

--
-- Name: market_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.market_type AS ENUM (
    'STOCK',
    'CRYPTO',
    'ETC'
);


ALTER TYPE public.market_type OWNER TO postgres;

--
-- Name: reasoning_tag; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.reasoning_tag AS ENUM (
    'TECHNICAL',
    'FUNDAMENTAL',
    'NEWS',
    'FEELING'
);


ALTER TYPE public.reasoning_tag OWNER TO postgres;

--
-- Name: strategy_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.strategy_type AS ENUM (
    'SCALPING',
    'SWING',
    'LONG_TERM',
    'UNKNOWN'
);


ALTER TYPE public.strategy_type OWNER TO postgres;

--
-- Name: trade_result; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.trade_result AS ENUM (
    'SUCCESS',
    'FAIL',
    'BREAKEVEN'
);


ALTER TYPE public.trade_result OWNER TO postgres;

--
-- Name: trade_type; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.trade_type AS ENUM (
    'BUY',
    'SELL'
);


ALTER TYPE public.trade_type OWNER TO postgres;

--
-- Name: current_user_id(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.current_user_id() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select nullif(current_setting('app.current_user_id', true), '')::uuid
$$;


ALTER FUNCTION public.current_user_id() OWNER TO postgres;

--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION public.set_updated_at() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounts; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    name text NOT NULL,
    broker text,
    cash_balance numeric(18,2) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.accounts FORCE ROW LEVEL SECURITY;


ALTER TABLE public.accounts OWNER TO invest_note_app;

--
-- Name: custom_tags; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.custom_tags (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    label text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.custom_tags FORCE ROW LEVEL SECURITY;


ALTER TABLE public.custom_tags OWNER TO invest_note_app;

--
-- Name: daily_close_prices; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.daily_close_prices (
    country_code text DEFAULT 'KR'::text NOT NULL,
    ticker text NOT NULL,
    close_date date NOT NULL,
    close_price numeric(15,2) NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.daily_close_prices OWNER TO invest_note_app;

--
-- Name: TABLE daily_close_prices; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.daily_close_prices IS '일별 종가 (자산 변화 페이지용). 전역 참조 데이터, RLS 미적용. data.go.kr getStockPriceInfo 증분 적재.';


--
-- Name: daily_price_sync_state; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.daily_price_sync_state (
    country_code text DEFAULT 'KR'::text NOT NULL,
    ticker text NOT NULL,
    checked_through_date date NOT NULL,
    checked_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.daily_price_sync_state OWNER TO invest_note_app;

--
-- Name: TABLE daily_price_sync_state; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.daily_price_sync_state IS '일별 종가 backfill 동기화 상태(종목별 조회 완료일). 전역 참조 데이터, RLS 미적용. 빈 응답 재질의 방지.';


--
-- Name: kis_tokens; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.kis_tokens (
    scope text NOT NULL,
    access_token text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.kis_tokens OWNER TO invest_note_app;

--
-- Name: TABLE kis_tokens; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.kis_tokens IS 'KIS 접근토큰 영속 저장소 (서버 전용 비밀). RLS enable + 정책 없음 = PostgREST 차단, BE(owner)만 접근.';


--
-- Name: nps_unmatched; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.nps_unmatched (
    nps_name text NOT NULL,
    nps_as_of date NOT NULL,
    holding_level text NOT NULL,
    resolved_ticker text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.nps_unmatched OWNER TO invest_note_app;

--
-- Name: TABLE nps_unmatched; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.nps_unmatched IS '국민연금 적재 시 종목명→ticker 매칭 실패분 reconcile 큐. 관리자가 확인 후 조치.';


--
-- Name: seed_source_state; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.seed_source_state (
    source text NOT NULL,
    fingerprint text NOT NULL,
    row_count integer DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.seed_source_state OWNER TO invest_note_app;

--
-- Name: TABLE seed_source_state; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.seed_source_state IS '종목 적재 소스별 마지막 fingerprint — 무변경 시 적재 skip.';


--
-- Name: stock_aliases; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.stock_aliases (
    country_code text NOT NULL,
    ticker text NOT NULL,
    alias text NOT NULL,
    alias_chosung text,
    source text DEFAULT 'manual'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.stock_aliases OWNER TO invest_note_app;

--
-- Name: TABLE stock_aliases; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.stock_aliases IS '종목 약칭/변형명 (검색 전용). source 로 수급 출처 구분.';


--
-- Name: stocks; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.stocks (
    country_code text DEFAULT 'KR'::text NOT NULL,
    ticker text NOT NULL,
    asset_name text NOT NULL,
    name_chosung text,
    currency text DEFAULT 'KRW'::text NOT NULL,
    exchange text,
    market text NOT NULL,
    sector text,
    is_active boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    naver_checked_at timestamp with time zone,
    source text,
    marcap bigint,
    marcap_rank integer,
    marcap_as_of date,
    nps_holding text,
    nps_as_of date,
    us_index text
);


ALTER TABLE public.stocks OWNER TO invest_note_app;

--
-- Name: TABLE stocks; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.stocks IS '주식 마스터 (검색/매칭용). 한국+해외 통합, 다중 소스 주기 적재. KIND/공공데이터/KRX/Naver 시드.';


--
-- Name: trades; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.trades (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    account_id uuid NOT NULL,
    asset_name text NOT NULL,
    market_type public.market_type DEFAULT 'STOCK'::public.market_type NOT NULL,
    trade_type public.trade_type NOT NULL,
    price numeric(18,4) NOT NULL,
    quantity numeric(18,4) NOT NULL,
    total_amount numeric(18,2) GENERATED ALWAYS AS ((price * quantity)) STORED,
    traded_at timestamp with time zone DEFAULT now() NOT NULL,
    strategy_type public.strategy_type,
    reasoning_tags public.reasoning_tag[] DEFAULT '{}'::public.reasoning_tag[],
    buy_reason text,
    sell_reason text,
    emotion public.emotion_type,
    result public.trade_result,
    profit_loss numeric(18,2),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    commission numeric(18,2) DEFAULT 0 NOT NULL,
    tax numeric(18,2) DEFAULT 0 NOT NULL,
    ticker_symbol text NOT NULL,
    country_code text DEFAULT 'KR'::text NOT NULL,
    avg_buy_price numeric(18,4),
    exchange text NOT NULL,
    holding_days integer,
    exchange_rate numeric(18,6) DEFAULT 1 NOT NULL,
    custom_tags text[] DEFAULT '{}'::text[] NOT NULL,
    CONSTRAINT trades_buy_reason_len_check CHECK (((buy_reason IS NULL) OR (char_length(buy_reason) <= 5000))),
    CONSTRAINT trades_exchange_rate_positive_check CHECK ((exchange_rate > (0)::numeric)),
    CONSTRAINT trades_sell_reason_len_check CHECK (((sell_reason IS NULL) OR (char_length(sell_reason) <= 5000)))
);

ALTER TABLE ONLY public.trades FORCE ROW LEVEL SECURITY;


ALTER TABLE public.trades OWNER TO invest_note_app;

--
-- Name: users; Type: TABLE; Schema: public; Owner: invest_note_app
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.users OWNER TO invest_note_app;

--
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: invest_note_app
--

COMMENT ON TABLE public.users IS '사용자 식별 FK 타깃 (신원은 Supabase Auth 소유). RLS enable + 정책 없음 = owner 만 접근.';


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: custom_tags custom_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.custom_tags
    ADD CONSTRAINT custom_tags_pkey PRIMARY KEY (id);


--
-- Name: custom_tags custom_tags_user_id_label_key; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.custom_tags
    ADD CONSTRAINT custom_tags_user_id_label_key UNIQUE (user_id, label);


--
-- Name: daily_close_prices daily_close_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.daily_close_prices
    ADD CONSTRAINT daily_close_prices_pkey PRIMARY KEY (country_code, ticker, close_date);


--
-- Name: daily_price_sync_state daily_price_sync_state_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.daily_price_sync_state
    ADD CONSTRAINT daily_price_sync_state_pkey PRIMARY KEY (country_code, ticker);


--
-- Name: kis_tokens kis_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.kis_tokens
    ADD CONSTRAINT kis_tokens_pkey PRIMARY KEY (scope);


--
-- Name: nps_unmatched nps_unmatched_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.nps_unmatched
    ADD CONSTRAINT nps_unmatched_pkey PRIMARY KEY (nps_name, nps_as_of);


--
-- Name: seed_source_state seed_source_state_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.seed_source_state
    ADD CONSTRAINT seed_source_state_pkey PRIMARY KEY (source);


--
-- Name: stock_aliases stock_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.stock_aliases
    ADD CONSTRAINT stock_aliases_pkey PRIMARY KEY (country_code, ticker, alias);


--
-- Name: stocks stocks_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.stocks
    ADD CONSTRAINT stocks_pkey PRIMARY KEY (country_code, ticker);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: accounts_user_id_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX accounts_user_id_idx ON public.accounts USING btree (user_id);


--
-- Name: custom_tags_user_id_label_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX custom_tags_user_id_label_idx ON public.custom_tags USING btree (user_id, label);


--
-- Name: daily_close_prices_ticker_date_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX daily_close_prices_ticker_date_idx ON public.daily_close_prices USING btree (ticker, close_date DESC);


--
-- Name: stock_aliases_alias_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX stock_aliases_alias_idx ON public.stock_aliases USING btree (alias);


--
-- Name: stock_aliases_chosung_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX stock_aliases_chosung_idx ON public.stock_aliases USING btree (alias_chosung);


--
-- Name: stocks_active_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX stocks_active_idx ON public.stocks USING btree (country_code, is_active);


--
-- Name: stocks_chosung_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX stocks_chosung_idx ON public.stocks USING btree (name_chosung);


--
-- Name: stocks_name_trgm_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX stocks_name_trgm_idx ON public.stocks USING gin (asset_name public.gin_trgm_ops);


--
-- Name: trades_account_id_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX trades_account_id_idx ON public.trades USING btree (account_id);


--
-- Name: trades_group_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX trades_group_idx ON public.trades USING btree (user_id, account_id, COALESCE(NULLIF(ticker_symbol, ''::text), asset_name), COALESCE(NULLIF(country_code, ''::text), 'KR'::text), traded_at);


--
-- Name: trades_user_id_traded_at_idx; Type: INDEX; Schema: public; Owner: invest_note_app
--

CREATE INDEX trades_user_id_traded_at_idx ON public.trades USING btree (user_id, traded_at DESC);


--
-- Name: accounts accounts_updated_at; Type: TRIGGER; Schema: public; Owner: invest_note_app
--

CREATE TRIGGER accounts_updated_at BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: trades trades_updated_at; Type: TRIGGER; Schema: public; Owner: invest_note_app
--

CREATE TRIGGER trades_updated_at BEFORE UPDATE ON public.trades FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: custom_tags custom_tags_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.custom_tags
    ADD CONSTRAINT custom_tags_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: stock_aliases stock_aliases_country_code_ticker_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.stock_aliases
    ADD CONSTRAINT stock_aliases_country_code_ticker_fkey FOREIGN KEY (country_code, ticker) REFERENCES public.stocks(country_code, ticker) ON DELETE CASCADE;


--
-- Name: trades trades_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: trades trades_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: invest_note_app
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: accounts; Type: ROW SECURITY; Schema: public; Owner: invest_note_app
--

ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;

--
-- Name: accounts accounts: 본인만 삭제; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "accounts: 본인만 삭제" ON public.accounts FOR DELETE USING ((public.current_user_id() = user_id));


--
-- Name: accounts accounts: 본인만 삽입; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "accounts: 본인만 삽입" ON public.accounts FOR INSERT WITH CHECK ((public.current_user_id() = user_id));


--
-- Name: accounts accounts: 본인만 수정; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "accounts: 본인만 수정" ON public.accounts FOR UPDATE USING ((public.current_user_id() = user_id)) WITH CHECK ((public.current_user_id() = user_id));


--
-- Name: accounts accounts: 본인만 조회; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "accounts: 본인만 조회" ON public.accounts FOR SELECT USING ((public.current_user_id() = user_id));


--
-- Name: custom_tags; Type: ROW SECURITY; Schema: public; Owner: invest_note_app
--

ALTER TABLE public.custom_tags ENABLE ROW LEVEL SECURITY;

--
-- Name: custom_tags custom_tags: 본인만 삭제; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "custom_tags: 본인만 삭제" ON public.custom_tags FOR DELETE USING ((public.current_user_id() = user_id));


--
-- Name: custom_tags custom_tags: 본인만 삽입; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "custom_tags: 본인만 삽입" ON public.custom_tags FOR INSERT WITH CHECK ((public.current_user_id() = user_id));


--
-- Name: custom_tags custom_tags: 본인만 조회; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "custom_tags: 본인만 조회" ON public.custom_tags FOR SELECT USING ((public.current_user_id() = user_id));


--
-- Name: kis_tokens; Type: ROW SECURITY; Schema: public; Owner: invest_note_app
--

ALTER TABLE public.kis_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: trades; Type: ROW SECURITY; Schema: public; Owner: invest_note_app
--

ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

--
-- Name: trades trades: 본인만 삭제; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "trades: 본인만 삭제" ON public.trades FOR DELETE USING ((public.current_user_id() = user_id));


--
-- Name: trades trades: 본인만 삽입; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "trades: 본인만 삽입" ON public.trades FOR INSERT WITH CHECK ((public.current_user_id() = user_id));


--
-- Name: trades trades: 본인만 수정; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "trades: 본인만 수정" ON public.trades FOR UPDATE USING ((public.current_user_id() = user_id)) WITH CHECK ((public.current_user_id() = user_id));


--
-- Name: trades trades: 본인만 조회; Type: POLICY; Schema: public; Owner: invest_note_app
--

CREATE POLICY "trades: 본인만 조회" ON public.trades FOR SELECT USING ((public.current_user_id() = user_id));


--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: invest_note_app
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO invest_note_app;


--
-- PostgreSQL database dump complete
--

\unrestrict 2CPTJf3HOZ7mbgh6OXlTmMy18a7rSnVJiMzAif6ni8hMFAOuu8rYfHL1vcrrS3c

