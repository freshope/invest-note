from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict

from invest_note_api.auth.dependency import get_current_user
from invest_note_api.auth.jwt import AuthenticatedUser
from invest_note_api.db import get_pool
from invest_note_api.db_ops import device_tokens_repo

router = APIRouter(prefix="/me")


class DeleteAccountRequest(BaseModel):
    # 고정 코드값만 허용(자유 텍스트 없음) — 임의 문자열 저장 시 어드민 사유 분포 버킷이
    # 오염되므로 Literal 로 강제한다. 미선택은 None.
    reason: Literal["not_useful", "not_using", "privacy", "other"] | None = None


class PushTokenRequest(BaseModel):
    # 푸시 토큰 등록 — platform 은 고정 코드값(ios|android)만. extra 키 거부.
    model_config = ConfigDict(extra="forbid")

    token: str
    platform: Literal["ios", "android"]


@router.get("")
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    return {"user_id": str(user.id), "email": user.email}


@router.post("/push-token", status_code=status.HTTP_204_NO_CONTENT)
async def register_push_token(
    body: PushTokenRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """푸시 토큰 등록 — (user_id, token) upsert(last_seen_at 갱신). 본문 없음(204).

    탈퇴 시 device_tokens 는 users FK CASCADE 로 자동 정리(별도 훅 불요). 로그아웃 기기별
    정리는 device_tokens_repo.delete_token 로 후속(현재 FE 미배선 — 토큰은 재로그인 시
    동일 값 upsert 로 재사용).
    """
    async with pool.acquire() as conn:
        await device_tokens_repo.upsert(
            conn, user_id=user.id, token=body.token, platform=body.platform
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    body: DeleteAccountRequest = DeleteAccountRequest(),
    user: AuthenticatedUser = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Response:
    """계정 삭제 — public.users 행 삭제(accounts/trades/custom_tags 는 FK cascade).

    인증은 BE 토큰-브로커 단일 경로이고 신원은 앱 DB(users/auth_identities)가 소유하므로,
    users 행 삭제가 곧 완전한 탈퇴다(별도 IdP 신원 제거 호출 없음). 재로그인 시 빈 상태로
    재프로비저닝된다.
    """
    # owner(plain acquire) 컨텍스트 — cascade 로 본인 데이터 정리.
    # 감사 INSERT 와 users DELETE 를 한 트랜잭션으로 묶어 한쪽만 남는 상태를 막는다.
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 감사 1건 INSERT 후 users DELETE. INSERT ... SELECT 라 users 행이 없으면(재시도)
            # 0 rows 삽입 → 탈퇴수 중복 집계 방지(signup_at 은 users.created_at 스냅샷).
            await conn.execute(
                "INSERT INTO public.account_deletions (user_id, signup_at, reason) "
                "SELECT id, created_at, $2 FROM public.users WHERE id = $1",
                user.id,
                body.reason,
            )
            # 탈퇴 전 표식: users DELETE 시 board_posts/board_comments.user_id 는 ON DELETE
            # SET NULL 로 끊겨 어드민이 '탈퇴한 회원' 글·댓글과 user_id 원래 null 인 공지를
            # 구분 못 한다. user_id 가 아직 살아있는 지금 author_withdrawn 을 스탬프한다
            # (board_posts 는 metadata jsonb merge, board_comments 는 전용 boolean 컬럼).
            await conn.execute(
                "UPDATE public.board_posts "
                "SET metadata = metadata || '{\"author_withdrawn\": true}'::jsonb "
                "WHERE user_id = $1",
                user.id,
            )
            await conn.execute(
                "UPDATE public.board_comments "
                "SET author_withdrawn = true "
                "WHERE user_id = $1",
                user.id,
            )
            await conn.execute("DELETE FROM public.users WHERE id = $1", user.id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
