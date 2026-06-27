"""OAuth 중개 라우터 (Phase 2b-1) — login/callback/token/refresh.

⚠️ 4개 엔드포인트 모두 **무인증**(로그인 진입점). main.py 가 /me·/v1(인증 보호) 보다 앞,
health(JWKS) 다음에 mount 한다.

flow(설계 노트):
  앱 → GET /auth/login?provider=&code_challenge= (인앱 브라우저)
     → BE 가 state+IdP verifier+앱 PKCE challenge 를 transient 저장 → IdP authorize 리다이렉트
  IdP → GET /auth/callback?code=&state=
     → state 검증(B11) → IdP code 교환+sub 추출(B-5) → (provider,sub)→원래 UUID 해석(B1)
     → BE access+refresh 발급(refresh 저장 B5) → 일회용 code 발급(B3)
     → 딥링크 {scheme}?code=<일회용> 리다이렉트(토큰 직접 미노출 B4) + profile upsert(B6)
  앱 → POST /auth/token {code, code_verifier}
     → 일회용 code consume(B3) + 앱 PKCE 대조(B12) → 저장된 access+refresh 반환
  앱 → POST /auth/refresh {refresh_token} → 회전(B5) + 신 access

함정: B1(고아화)·B3(replay)·B4(토큰 미노출)·B5(refresh)·B10(sub)·B11(state)·B12(app PKCE).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from invest_note_api.auth import token_store
from invest_note_api.auth.be_token import mint_be_token
from invest_note_api.auth.oauth_providers import ProviderNotConfigured, get_provider
from invest_note_api.auth.pkce import verify_s256
from invest_note_api.config import Settings, get_settings
from invest_note_api.db import get_pool
from invest_note_api.errors import (
    ERR_REQUEST_FALLBACK,
    ERR_SERVICE_UNAVAILABLE,
    ERR_UNAUTHORIZED,
    APIError,
)
from invest_note_api.external.http_client import get_http_client
from invest_note_api.services.auth_identity import (
    create_user_identity,
    link_user_by_verified_email,
    resolve_user_id,
)
from invest_note_api.services.user_profile import upsert_profile

router = APIRouter(prefix="/auth")

# 일회용 code / state transient kind.
_KIND_STATE = "state"
_KIND_CODE = "code"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _redirect_uri(settings: Settings) -> str:
    # IdP redirect_uri = BE callback 고정(딥링크 아님).
    return f"{settings.be_oauth_redirect_base}/auth/callback"


def _redirect_with_code(target: str, code: str) -> str:
    """리다이렉트 대상(앱 딥링크 scheme 또는 어드민 웹 callback URL)에 일회용 code query 를
    안전하게 부착(F12). 양쪽이 동형이라 단일 헬퍼로 공유한다(B4 — code 만, 토큰 미노출).

    query 는 fragment(#) **앞**에 와야 한다(뒤에 붙으면 앱 파서가 못 읽는다). 기존 query 가 있으면
    '&', 없으면 '?'. 운영 env 오설정(target 에 #fragment 포함)에도 로그인 실패하지 않게 한다.
    어드민 web 은 클라가 URL 미전송·고정 env(target)만 매핑 → open redirect 차단.
    """
    base, sep, fragment = target.partition("#")
    q = "&" if "?" in base else "?"
    qs = urlencode({"code": code})
    return f"{base}{q}{qs}" + (f"#{fragment}" if sep else "")


@router.get("/login", include_in_schema=False)
async def login(
    provider: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    client: str = "native",
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
) -> RedirectResponse:
    """IdP authorize 리다이렉트. state+IdP verifier+앱 PKCE challenge 를 transient 저장(B11/B12).

    code_challenge = 앱↔BE PKCE(Layer2, B12) — 앱이 생성해 보낸다(2b-1 필수). S256 만 허용.
    client = web/native 구분(기본 native=딥링크, 무회귀). "admin" = 어드민 웹 패널 →
    callback 이 be_admin_redirect_url 로 2차 hop. state 에 저장해 callback 이 분기.
    """
    if code_challenge_method != "S256":
        raise APIError(ERR_REQUEST_FALLBACK, 400)
    # client=admin 인데 redirect env 가 빈 값이면 IdP 왕복·state 소모 전에 503(dormant-503).
    if client == "admin" and not settings.be_admin_redirect_url:
        raise APIError(ERR_SERVICE_UNAVAILABLE, 503)
    try:
        provider_client = get_provider(provider, settings)
    except KeyError:
        raise APIError(ERR_REQUEST_FALLBACK, 400)  # 미등록 provider 이름
    except ProviderNotConfigured:
        raise APIError("지원하지 않는 로그인 수단입니다.", 503)  # 자격증명 미설정(부분 활성)

    state = token_store.generate_token()
    idp_verifier = token_store.generate_token()  # Layer1(BE↔IdP) PKCE verifier
    async with pool.acquire() as conn:
        await token_store.put_transient(
            conn, state, _KIND_STATE,
            {
                "provider": provider,
                "idp_verifier": idp_verifier,
                "app_code_challenge": code_challenge,  # Layer2(앱↔BE) — /auth/token 에서 대조
                "client": client,  # callback 이 web(admin)/native 분기에 사용
            },
            _now() + timedelta(seconds=settings.oauth_state_ttl),
        )
    url = provider_client.build_authorize_url(
        state=state, idp_verifier=idp_verifier, redirect_uri=_redirect_uri(settings)
    )
    return RedirectResponse(url, status_code=302)


def _apple_user_display_name(user_field: str | None) -> str | None:
    """Apple form_post `user` 필드(JSON) → display_name.

    ⚠️ Apple 은 이름/email 을 **첫 인증의 form_post body 에만** 준다(id_token 미포함). 이 경로를
    안 읽으면 신규 Apple 유저의 display_name 을 영영 못 받는다(기존 유저는 백필이 커버). 첫 인증이
    아니면 user 필드 부재 → None(B6 COALESCE 가 기존값 보존).
    """
    if not user_field:
        return None
    try:
        u = json.loads(user_field)
    except (ValueError, TypeError):
        return None
    name = u.get("name") if isinstance(u, dict) else None
    if not isinstance(name, dict):
        return None
    parts = [name.get("firstName"), name.get("lastName")]
    full = " ".join(p for p in parts if p)
    return full or None


@router.get("/callback", include_in_schema=False)
async def callback_get(
    code: str,
    state: str,
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
    http: httpx.AsyncClient = Depends(get_http_client),
) -> RedirectResponse:
    """Google/Kakao callback — query GET(authorization code 흐름)."""
    return await _handle_callback(code, state, settings, pool, http)


@router.post("/callback", include_in_schema=False)
async def callback_post(
    request: Request,
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
    http: httpx.AsyncClient = Depends(get_http_client),
) -> RedirectResponse:
    """Apple callback — form_post(POST body). ⚠️ Apple 은 scope(name/email) 요청 시 callback 을
    application/x-www-form-urlencoded POST 로 보낸다(GET 아님). 첫 인증 시 `user`(이름 JSON)도 동봉.
    """
    form = await request.form()
    code = form.get("code")
    state = form.get("state")
    if not code or not state:
        raise APIError(ERR_REQUEST_FALLBACK, 400)
    return await _handle_callback(
        str(code), str(state), settings, pool, http,
        apple_display_name=_apple_user_display_name(form.get("user")),
    )


async def _handle_callback(
    code: str,
    state: str,
    settings: Settings,
    pool: asyncpg.Pool,
    http: httpx.AsyncClient,
    *,
    apple_display_name: str | None = None,
) -> RedirectResponse:
    """IdP code 교환 + (provider,sub)→UUID 해석 + 토큰 발급 + 일회용 code 딥링크. GET/POST 공유."""
    # F15: BE 토큰 발급이 dormant(signing key 없음)면 mint_be_token 이 RuntimeError→500. OAuth
    # 엔드포인트는 503(서비스 비활성)으로 명시 — 부분배포/env 누락 시 500 노출 방지.
    if not settings.be_token_enabled:
        raise APIError(ERR_SERVICE_UNAVAILABLE, 503)

    async with pool.acquire() as conn:
        # B11: state single-use consume(위조/replay 거부).
        st = await token_store.consume_transient(conn, state, _KIND_STATE)
    if st is None:
        raise APIError(ERR_UNAUTHORIZED, 401)  # state 불일치/만료/소비됨

    provider = st["provider"]
    # state 에 저장된 client(web/native). 구 in-flight state(키 부재)는 native 로 폴백(무회귀).
    client_kind = st.get("client", "native")
    # F4: get_provider 예외 매핑(login 과 대칭) — KeyError/미설정이 500(state 이미 소비) 되지 않게.
    try:
        provider_client = get_provider(provider, settings)
    except KeyError:
        raise APIError(ERR_REQUEST_FALLBACK, 400)
    except ProviderNotConfigured:
        raise APIError(ERR_SERVICE_UNAVAILABLE, 503)
    sub, userinfo = await provider_client.fetch_identity(
        code=code, idp_verifier=st["idp_verifier"],
        redirect_uri=_redirect_uri(settings), http=http,
    )

    # Apple 첫 인증 form_post 의 이름은 id_token 에 없어 여기서 보강(B6 — None 이면 미보강).
    display_name = userinfo.display_name or apple_display_name

    async with pool.acquire() as conn:
        # 매핑 해석. hit = 기존자 → 원래 UUID 재사용(데이터 보존, B1). miss = (provider,sub) 신규.
        # ⚠️ gapless 전제: cutover 시 Supabase 신규가입 동결 후 최종 백필로 매핑 완전·확정 →
        # 미매핑 sub 는 기존자가 아님(고아화 없음). 클라이언트 BE flow 노출(B안: 서버 플래그
        # flip)은 백필 완료 후(운영 runbook 가드 — flip 시점이 신규 생성 시작점).
        user_id = await resolve_user_id(conn, provider, sub)
        if user_id is None:
            # B1-link: (provider,sub) miss 라도 같은 verified 이메일의 기존 계정이 있으면 자동 연결
            # (카카오↔구글 동일 이메일 중복 계정 방지). 양쪽-verified 가드, 매칭 없으면 신규 생성 폴백.
            user_id = await link_user_by_verified_email(
                conn, provider, sub,
                email=userinfo.email, email_verified=userinfo.email_verified,
            )
        if user_id is None:
            user_id = await create_user_identity(conn, provider, sub)

        # BE access(sub=기존자 원래 UUID 또는 신규 가입 UUID) + refresh 발급. refresh 는 해시 저장(B5).
        access = mint_be_token(user_id, userinfo.email, settings=settings)
        refresh = token_store.generate_token()
        one_time = token_store.generate_token()
        # F16: save_refresh + put_transient + upsert_profile 를 한 트랜잭션으로 — upsert 예외 시
        # refresh 해시 고아 행(좀비)이 남지 않게 원자화.
        async with conn.transaction():
            await token_store.save_refresh(
                conn, user_id, refresh,
                _now() + timedelta(seconds=settings.be_refresh_token_ttl),
            )

            # 일회용 code 발급 — 딥링크엔 이 code 만(토큰 직접 미노출, B4). /auth/token 에서 교환.
            # 앱 PKCE challenge(Layer2, B12)를 code payload 에 이월 → /auth/token 이 verifier 와 대조.
            await token_store.put_transient(
                conn, one_time, _KIND_CODE,
                {
                    "access_token": access,
                    "refresh_token": refresh,
                    "app_code_challenge": st["app_code_challenge"],
                },
                _now() + timedelta(seconds=settings.oauth_code_ttl),
            )

            # profile upsert(B6 COALESCE) — last_sign_in 항상, 나머지 null 이면 보존.
            await upsert_profile(
                conn, user_id,
                email=userinfo.email,
                display_name=display_name,
                avatar_url=userinfo.avatar_url,
                email_verified=userinfo.email_verified,
                provider=provider,
                last_sign_in=_now(),
            )

    # client 별 2차 hop — code 만(B4). client 가 /auth/token 으로 교환.
    # admin(웹) → be_admin_redirect_url, 그 외(default native) → 딥링크.
    if client_kind == "admin":
        # login 이 503 fail-fast 하므로 도달 시 env 가 채워져 있어야 한다. 방어적: 비어 있으면
        # (login~callback 사이 env 제거 등 극단) 브라우저가 못 여는 네이티브 딥링크로 폴백하지
        # 말고 503 — silent 실패(빈 화면) 대신 진단 가능한 에러로.
        if not settings.be_admin_redirect_url:
            raise APIError(ERR_SERVICE_UNAVAILABLE, 503)
        target = _redirect_with_code(settings.be_admin_redirect_url, one_time)
    else:
        target = _redirect_with_code(settings.be_deeplink_scheme, one_time)
    return RedirectResponse(target, status_code=302)


class TokenRequest(BaseModel):
    code: str
    # ⚠️ B12: 앱↔BE PKCE verifier — /auth/login 의 challenge 와 대조(필수, enforce-always).
    # 2b-1 엔 broker flow 소비 클라이언트가 0(FE swap=2b-2)이라 필수화가 expand 를 위배하지 않음.
    code_verifier: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


@router.post("/token")
async def token(
    body: TokenRequest,
    pool: asyncpg.Pool = Depends(get_pool),
) -> TokenResponse:
    """일회용 code → access+refresh 교환. B3 single-use + B12 앱 PKCE 대조.

    ⚠️ F1(HINGE): PKCE 검증을 consume **전에** 한다 — peek(미소비 조회) → S256 대조 → 통과 시에만
    consume(단일 소비). 가로챈 code+틀린 verifier 호출이 code 를 먼저 태워(이전 구현) 정당 앱 교환을
    401(DoS)시키던 것을 차단. single-use 는 consume 의 원자적 DELETE 가 보장(검증 후).
    """
    async with pool.acquire() as conn:
        # 미소비 조회만(consume 아님) — PKCE 검증 전이라 code 를 태우지 않는다.
        peeked = await token_store.peek_transient(conn, body.code, _KIND_CODE)
        if peeked is None:
            raise APIError(ERR_UNAUTHORIZED, 401)  # code 만료/소비됨/위조(B3 replay)

        # B12: 앱 PKCE 대조 — callback 이 code payload 에 이월한 challenge 와 verifier 를 S256 대조.
        # challenge 누락/불일치 = 거부(enforce-always). 실패 시 code 미소비(정당 앱이 재교환 가능).
        challenge = peeked.get("app_code_challenge")
        if not challenge or not verify_s256(challenge, body.code_verifier):
            raise APIError(ERR_UNAUTHORIZED, 401)

        # 검증 통과 → 원자적 단일 소비(동시 2회 시 1회만 성공, replay 거부).
        payload = await token_store.consume_transient(conn, body.code, _KIND_CODE)
    if payload is None:
        raise APIError(ERR_UNAUTHORIZED, 401)  # peek↔consume 사이 race/만료

    return TokenResponse(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
    )


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """refresh token 서버측 무효화(세션 종료). refresh 소유 자체가 증명이라 무인증(refresh 와 동일).

    멱등 — 무효/이미-revoked 토큰도 200(클라가 항상 로컬 정리를 이어가게). 토큰 존재 여부를
    노출하지 않게 항상 200 + {revoked} bool. access 는 단명(1h) stateless 라 revoke 대상 아님.
    """
    async with pool.acquire() as conn:
        revoked = await token_store.revoke_refresh(conn, body.refresh_token)
    return {"revoked": revoked}


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    settings: Settings = Depends(get_settings),
    pool: asyncpg.Pool = Depends(get_pool),
) -> TokenResponse:
    """refresh 회전(B5) — 구 무효화 + 신 발급 + 신 access. 무효 refresh → 401."""
    # F15: dormant 면 mint_be_token 이 RuntimeError→500. 503 으로 명시(부분배포/env 누락 방어).
    if not settings.be_token_enabled:
        raise APIError(ERR_SERVICE_UNAVAILABLE, 503)
    new_refresh = token_store.generate_token()
    async with pool.acquire() as conn:
        async with conn.transaction():
            user_id = await token_store.rotate_refresh(
                conn, body.refresh_token, new_refresh,
                _now() + timedelta(seconds=settings.be_refresh_token_ttl),
            )
            if user_id is None:
                raise APIError(ERR_UNAUTHORIZED, 401)  # 만료/이미회전/없음
            # 신 access — email 은 profile 에서 조회(refresh 경로엔 IdP userinfo 없음).
            row = await conn.fetchrow(
                "SELECT email FROM user_profiles WHERE user_id = $1", user_id
            )
            email = row["email"] if row else None
    access = mint_be_token(user_id, email, settings=settings)
    return TokenResponse(access_token=access, refresh_token=new_refresh)
