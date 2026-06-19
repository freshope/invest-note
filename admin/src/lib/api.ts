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

/** 대시보드 카운트. 키는 snake_case 유지(BE AdminStats 와 동일). */
export interface AdminStats {
  users: number;
  accounts: number;
  trades: number;
  stocks: number;
  nps_unmatched: number;
}

/** 일별 누적 가입자 수 한 점. date 는 KST 가입일(YYYY-MM-DD), BE UserGrowthPoint 와 정합. */
export interface UserGrowthPoint {
  date: string;
  cumulative: number;
}

/** 목록 쿼리 파라미터(전 테이블 공통). page 1-base, page_size 기본 50·최대 200(서버 clamp). */
export interface AdminListParams {
  page?: number;
  page_size?: number;
  q?: string;
}

function listQuery(params?: AdminListParams): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  if (params.page != null) sp.set("page", String(params.page));
  if (params.page_size != null) sp.set("page_size", String(params.page_size));
  if (params.q) sp.set("q", params.q);
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

// ⚠️ users 에 email 컬럼 없음(신원은 Supabase Auth 소유). row = { id, created_at }.
export interface UserRow extends BaseRow {
  id: string;
  created_at: string;
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
export interface BoardRow extends BaseRow {
  id: string;
  board_type: BoardType;
  user_id: string | null;
  title: string;
  body: string;
  status: string;
  is_pinned: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// board_comments row(7키). is_admin 으로 관리자 댓글 구분.
export interface BoardComment extends BaseRow {
  id: string;
  post_id: string;
  user_id: string | null;
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

function boardListQuery(params?: BoardListParams): string {
  const sp = new URLSearchParams();
  if (params?.board_type) sp.set("board_type", params.board_type);
  if (params?.page != null) sp.set("page", String(params.page));
  if (params?.page_size != null) sp.set("page_size", String(params.page_size));
  if (params?.q) sp.set("q", params.q);
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

// ============================================================
// API
// ============================================================

export const adminApi = {
  // 어드민(allowlist) 여부 프로브. 비-admin 은 BE require_admin 이 403 → ApiError(403).
  me: () => apiFetch<{ email: string | null }>("/admin/me"),

  stats: () => apiFetch<AdminStats>("/admin/stats"),

  userGrowth: () => apiFetch<UserGrowthPoint[]>("/admin/user-growth"),

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

  boards: {
    list: (params?: BoardListParams) =>
      apiFetch<AdminListResponse<BoardRow>>(
        `/admin/boards${boardListQuery(params)}`,
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
  },
};
