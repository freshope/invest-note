// FastAPI 어드민 클라이언트.
// 경로 규약: bare /admin/* 호출(app 의 /v1 prefix 미적용). 인증: lib/auth 의 getAccessToken() 으로 Bearer 주입.
// row 응답은 BE 가 DB 컬럼을 snake_case 그대로 통과한다(A2) — FE 는 camelCase 매핑을 하지 않는다.
import { getAccessToken } from "@/lib/auth";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// NEXT_PUBLIC_API_BASE_URL: FastAPI 서버 주소. 정적 export 환경에서는 필수.
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(
  /\/$/,
  "",
);

async function getBearerHeader(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const bearer = await getBearerHeader();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...bearer,
      ...(init?.headers ?? {}),
    },
  });
  // 204 No Content(DELETE 등)는 본문 없음.
  if (res.status === 204) {
    if (!res.ok) throw new ApiError(`API 오류 (${res.status})`, res.status);
    return undefined as T;
  }
  const data = await res.json();
  if (!res.ok) {
    throw new ApiError(
      (data as { error?: string }).error ?? `API 오류 (${res.status})`,
      res.status,
    );
  }
  return data as T;
}

// ============================================================
// 공통 타입 (BE schemas/admin.py 와 정합)
// ============================================================

/** 전 테이블 공통 목록 엔벨로프. items 는 snake_case row dict, total 은 검색 적용 전체 건수. */
export interface AdminListResponse<T> {
  items: T[];
  total: number;
}

/** 대시보드 카운트. 키는 snake_case 유지(BE AdminStats 와 동일).
 *  *_today 는 KST 당일 등록분, dau/wau/mau 는 last_sign_in 기준 로그인 활성(rolling 1/7/30일). */
export interface AdminStats {
  users: number;
  users_today: number;
  accounts: number;
  accounts_today: number;
  trades: number;
  trades_today: number;
  stocks: number;
  nps_unmatched: number;
  broker_statements: number;
  broker_statements_today: number;
  feedback: number;
  feedback_today: number;
  bug_reports: number;
  bug_reports_today: number;
  deletions: number;
  deletions_today: number;
  dau: number;
  wau: number;
  mau: number;
}

/** 일별 가입자 한 점. date 는 KST 가입일(YYYY-MM-DD), BE UserGrowthPoint 와 정합. */
export interface UserGrowthPoint {
  date: string;
  cumulative: number;
  // 해당 날짜의 신규 가입자 수(0 포함). generate_series 로 빈 날도 0 으로 채워짐.
  new_users: number;
}

/** 일별 탈퇴 수 한 점. date 는 KST 탈퇴일(YYYY-MM-DD), BE DeletionTrendPoint 와 정합. */
export interface DeletionTrendPoint {
  date: string;
  deletions: number;
}

/** 탈퇴 사유별 건수. reason 미선택은 'unspecified'. BE DeletionReasonCount 와 정합. */
export interface DeletionReasonCount {
  reason: string;
  count: number;
}

/** 회원 탈퇴 통계(BE AccountDeletionStats 와 정합, 키 snake_case).
 *  churn_rate = total_deletions / (total_users + total_deletions), 0~1. */
export interface AccountDeletionStats {
  total_users: number;
  total_deletions: number;
  churn_rate: number;
  deletions_30d: number;
  avg_lifetime_days: number | null;
  trend: DeletionTrendPoint[];
  reasons: DeletionReasonCount[];
}

/** 목록 쿼리 파라미터(전 테이블 공통). page 1-base, page_size 기본 50·최대 200(서버 clamp). */
export interface AdminListParams {
  page?: number;
  page_size?: number;
  q?: string;
}

function listQuery(
  params?: AdminListParams,
  extra?: Record<string, string | undefined>,
): string {
  const sp = new URLSearchParams();
  if (params?.page != null) sp.set("page", String(params.page));
  if (params?.page_size != null) sp.set("page_size", String(params.page_size));
  if (params?.q) sp.set("q", params.q);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) if (v) sp.set(k, v);
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

// ============================================================
// Row 타입 — DB 컬럼 snake_case passthrough.
// 실제 컬럼 집합은 BE routers/admin.py(#8)·실제 테이블 기준. 미확정 필드는 인덱스 시그니처로 수용.
// ============================================================

interface BaseRow {
  // snake_case 컬럼 passthrough. 페이지가 참조하는 컬럼만 아래에 명시하고 나머지는 통과.
  [key: string]: unknown;
}

// users(id, created_at) LEFT JOIN user_profiles — 프로필 컬럼은 행이 없으면 null.
export interface UserRow extends BaseRow {
  id: string;
  created_at: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  email_verified: boolean | null;
  providers: string[] | null;
  last_sign_in: string | null;
  // 서브쿼리 집계 — 보유 계좌수·총 거래수(항상 0 이상).
  account_count: number;
  trade_count: number;
}

export interface AccountRow extends BaseRow {
  id: string;
  name: string;
}

export interface TradeRow extends BaseRow {
  id: string;
  ticker_symbol: string | null;
  asset_name: string | null;
}

export interface CustomTagRow extends BaseRow {
  id: string;
  label: string;
}

// ⚠️ stocks PK = 복합 (country_code, ticker). 수정 URL 조립에 둘 다 필요.
export interface StockRow extends BaseRow {
  country_code: string;
  ticker: string;
  asset_name: string | null;
  market: string | null;
}

// ⚠️ nps_unmatched 에 id 없음. PK = 복합 (nps_name, nps_as_of).
export interface NpsUnmatchedRow extends BaseRow {
  nps_name: string;
  nps_as_of: string;
  holding_level: string;
  resolved_ticker: string | null;
}

// ============================================================
// 게시판(board) — 멀티 게시판(board_type discriminator). snake_case passthrough.
// ============================================================

export type BoardType = "notice" | "feedback" | "bug_report" | "broker_statement";

// board_posts row(10키). status 는 BE 에서 자유 텍스트(Literal 아님).
// author_* 는 user_profiles LEFT JOIN 노출(프로필 행 없으면 null).
export interface BoardRow extends BaseRow {
  id: string;
  board_type: BoardType;
  user_id: string | null;
  author_display_name: string | null;
  author_avatar_url: string | null;
  title: string;
  body: string;
  status: string;
  is_pinned: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// board_comments row. is_admin 으로 관리자 댓글 구분.
// author_* 는 user_profiles LEFT JOIN 노출(프로필 행 없으면 null).
// author_withdrawn 은 작성자 탈퇴 시 스탬프(user_id SET NULL 로 끊기기 전 표식).
export interface BoardComment extends BaseRow {
  id: string;
  post_id: string;
  user_id: string | null;
  author_display_name: string | null;
  author_avatar_url: string | null;
  author_withdrawn: boolean;
  is_admin: boolean;
  body: string;
  created_at: string;
  updated_at: string;
}

// board_attachments row(10키). 이번 스펙은 메타 뷰어뿐(다운로드/업로드 없음).
export interface BoardAttachment extends BaseRow {
  id: string;
  post_id: string | null;
  comment_id: string | null;
  user_id: string | null;
  original_name: string;
  content_type: string | null;
  size_bytes: number | null;
  storage_key: string | null;
  bucket: string | null;
  created_at: string;
}

// 상세 = post 10키 + 조인된 댓글/첨부.
export type BoardDetail = BoardRow & {
  comments: BoardComment[];
  attachments: BoardAttachment[];
};

// ============================================================
// 거래내역서 원장(import ledger) — batches(파일 1건=1행) + entries(행 append-only).
// snake_case passthrough. numeric 컬럼은 BE 가 문자열/숫자로 줄 수 있어 fmtNum 으로 표시.
// ============================================================

// import_batches 목록 행. email·account_name 은 LEFT JOIN, *_count 는 서브쿼리 집계.
export interface ImportBatchRow extends BaseRow {
  id: string;
  broker_key: string;
  filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  account_hint: string | null;
  account_id: string | null;
  account_name: string | null;
  committed_at: string | null; // null = 미리보기만(미등록)
  created_at: string;
  parsed_at: string | null;
  email: string | null;
  entry_count: number;
  trade_row_count: number;
}

// import_ledger_entries 행(append-only). raw 는 파싱 원문 전체(jsonb→object).
export interface ImportLedgerEntry extends BaseRow {
  id: string;
  source_row_no: number;
  traded_at_raw: string | null;
  traded_at: string | null;
  trade_type: string | null;
  asset_name: string | null;
  ticker_hint: string | null;
  isin: string | null;
  country_code: string | null;
  quantity: string | number | null;
  price: string | number | null;
  commission: string | number | null;
  tax: string | number | null;
  exchange_rate: string | number | null;
  raw: Record<string, unknown>;
  created_at: string;
}

// 상세 = 배치 메타(목록 + 원문 식별 컬럼) + 원장 행 전량. BE ImportBatchDetail 과 정합.
export interface ImportBatchDetail {
  batch: ImportBatchRow & {
    user_id: string | null;
    parser_version: string;
    storage_key: string | null;
    content_sha256: string;
  };
  entries: ImportLedgerEntry[];
}

// ============================================================
// 쓰기 입력 (BE 화이트리스트와 정합 — extra='forbid')
// ============================================================

export interface StockUpdateInput {
  asset_name?: string | null;
  market?: string | null;
  exchange?: string | null;
  sector?: string | null;
  currency?: string | null;
  is_active?: boolean | null;
  us_index?: string | null;
}

export interface NpsUnmatchedCreateInput {
  nps_name: string;
  nps_as_of: string;
  holding_level: string;
  resolved_ticker?: string | null;
}

export interface NpsUnmatchedUpdateInput {
  holding_level?: string | null;
  resolved_ticker?: string | null;
}

// board 쓰기 입력(BE schemas/board.py extra='forbid' 와 정합).
export interface BoardPostCreateInput {
  board_type: BoardType;
  title: string;
  body?: string;
  metadata?: Record<string, unknown>;
  is_pinned?: boolean;
}

// board_type 수정 불가(생략).
export interface BoardPostUpdateInput {
  title?: string;
  body?: string;
  status?: string;
  is_pinned?: boolean;
}

export interface BoardCommentCreateInput {
  body: string;
}

// board 목록 파라미터(공통 + board_type 필터).
export interface BoardListParams extends AdminListParams {
  board_type?: BoardType;
}

// ============================================================
// API
// ============================================================

export const adminApi = {
  // 어드민(allowlist) 여부 프로브. 비-admin 은 BE require_admin 이 403 → ApiError(403).
  me: () => apiFetch<{ email: string | null }>("/admin/me"),

  stats: () => apiFetch<AdminStats>("/admin/stats"),

  userGrowth: () => apiFetch<UserGrowthPoint[]>("/admin/user-growth"),

  deletionStats: () =>
    apiFetch<AccountDeletionStats>("/admin/deletion-stats"),

  users: (params?: AdminListParams) =>
    apiFetch<AdminListResponse<UserRow>>(`/admin/users${listQuery(params)}`),

  accounts: (params?: AdminListParams) =>
    apiFetch<AdminListResponse<AccountRow>>(
      `/admin/accounts${listQuery(params)}`,
    ),

  trades: (params?: AdminListParams) =>
    apiFetch<AdminListResponse<TradeRow>>(`/admin/trades${listQuery(params)}`),

  customTags: (params?: AdminListParams) =>
    apiFetch<AdminListResponse<CustomTagRow>>(
      `/admin/custom-tags${listQuery(params)}`,
    ),

  stocks: {
    list: (params?: AdminListParams) =>
      apiFetch<AdminListResponse<StockRow>>(`/admin/stocks${listQuery(params)}`),
    // PK = 복합 (country_code, ticker). seed 가 덮어쓰지 않는 필드만 수정 가능(BE StockUpdate 화이트리스트).
    update: (
      key: { country_code: string; ticker: string },
      input: StockUpdateInput,
    ) =>
      apiFetch<StockRow>(
        `/admin/stocks/${encodeURIComponent(key.country_code)}/${encodeURIComponent(key.ticker)}`,
        { method: "PATCH", body: JSON.stringify(input) },
      ),
  },

  npsUnmatched: {
    list: (params?: AdminListParams) =>
      apiFetch<AdminListResponse<NpsUnmatchedRow>>(
        `/admin/nps-unmatched${listQuery(params)}`,
      ),
    create: (input: NpsUnmatchedCreateInput) =>
      apiFetch<NpsUnmatchedRow>("/admin/nps-unmatched", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    // 식별자 = 복합 PK(nps_name, nps_as_of). 경로/쿼리 식별 방식은 BE routers(#8) 확정 후 정렬.
    update: (
      key: { nps_name: string; nps_as_of: string },
      input: NpsUnmatchedUpdateInput,
    ) =>
      apiFetch<NpsUnmatchedRow>(
        `/admin/nps-unmatched?${new URLSearchParams({ nps_name: key.nps_name, nps_as_of: key.nps_as_of })}`,
        { method: "PATCH", body: JSON.stringify(input) },
      ),
    remove: (key: { nps_name: string; nps_as_of: string }) =>
      apiFetch<void>(
        `/admin/nps-unmatched?${new URLSearchParams({ nps_name: key.nps_name, nps_as_of: key.nps_as_of })}`,
        { method: "DELETE" },
      ),
  },

  // 거래내역서 원장 — 읽기 전용. 목록은 제네릭 /admin/import-batches, 상세는 전용 엔드포인트.
  importBatches: {
    list: (params?: AdminListParams) =>
      apiFetch<AdminListResponse<ImportBatchRow>>(
        `/admin/import-batches${listQuery(params)}`,
      ),
    get: (batchId: string) =>
      apiFetch<ImportBatchDetail>(
        `/admin/import-batches/${encodeURIComponent(batchId)}`,
      ),
  },

  boards: {
    list: (params?: BoardListParams) =>
      apiFetch<AdminListResponse<BoardRow>>(
        `/admin/boards${listQuery(params, { board_type: params?.board_type })}`,
      ),
    get: (postId: string) =>
      apiFetch<BoardDetail>(`/admin/boards/${encodeURIComponent(postId)}`),
    create: (input: BoardPostCreateInput) =>
      apiFetch<BoardRow>("/admin/boards", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    update: (postId: string, input: BoardPostUpdateInput) =>
      apiFetch<BoardRow>(`/admin/boards/${encodeURIComponent(postId)}`, {
        method: "PATCH",
        body: JSON.stringify(input),
      }),
    remove: (postId: string) =>
      apiFetch<void>(`/admin/boards/${encodeURIComponent(postId)}`, {
        method: "DELETE",
      }),
    addComment: (postId: string, input: BoardCommentCreateInput) =>
      apiFetch<BoardComment>(
        `/admin/boards/${encodeURIComponent(postId)}/comments`,
        { method: "POST", body: JSON.stringify(input) },
      ),
    removeComment: (commentId: string) =>
      apiFetch<void>(
        `/admin/boards/comments/${encodeURIComponent(commentId)}`,
        { method: "DELETE" },
      ),
    // 첨부 다운로드 — presigned GET URL(JSON). SPA 가 window.open 으로 새 탭 열기.
    attachmentDownloadUrl: (attachmentId: string) =>
      apiFetch<{ download_url: string }>(
        `/admin/boards/attachments/${encodeURIComponent(attachmentId)}/download`,
      ),
  },
};
