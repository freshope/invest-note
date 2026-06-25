"""Cloudflare R2(S3 호환) 헬퍼 — 거래내역서 제보 첨부 스토리지.

R2 는 OTA 매니페스트 호스팅에 이미 쓰는 객체 스토리지다. 업로드는 2단계:
  1) presign PUT 으로 `temp/{user_id}/{uuid}.{ext}` 에 클라이언트가 직접 올린다(BE 는 서명만,
     로컬 SigV4 = 네트워크 0).
  2) 등록(submit) 시 BE 가 `broker_statement/{user_id}/...` 로 **서버측 copy** 한다(promote).
미등록 temp 객체(업로드만 하고 등록 안 함)는 R2 의 `temp/` prefix lifecycle 규칙이 청소한다.

보안 불변식: temp key 는 서버가 생성하고(build_temp_key), 라우터가 `temp/{user_id}/` prefix 를
재검증한다(남 user/임의 key 차단). final key 는 promote_key 로 temp 에서 결정 — 클라이언트가
정식 위치를 지정할 수 없다.

⚠️ copy_object/delete_object 는 **동기 네트워크 호출**(presign 과 달리 실제 R2 왕복)이다.
async 핸들러에서는 반드시 run_in_threadpool 등으로 감싸 이벤트 루프 블로킹을 피한다.

dormant: r2 미설정(자격증명 4개 중 하나라도 없음)이면 진입 시 APIError(503).
make_client 는 자격증명을 명시 전달하고 SigV4 를 고정한다 — 명시하지 않으면 boto3 가
env/IMDS 를 네트워크로 뒤져 hang 할 수 있다.
"""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from invest_note_api.config import Settings
from invest_note_api.errors import APIError

# 업로드 스테이징 / 정식 보관 prefix. temp 는 lifecycle 청소 대상.
TEMP_PREFIX = "temp"
STATEMENT_PREFIX = "broker_statement"
BUG_REPORT_PREFIX = "bug_report"

ERR_R2_DISABLED = "첨부 스토리지가 설정되지 않았습니다."
ERR_UPLOAD_MISSING = "업로드가 완료되지 않았습니다. 다시 시도해주세요."


def _ensure_enabled(settings: Settings) -> None:
    if not settings.r2_enabled:
        raise APIError(ERR_R2_DISABLED, 503)


@lru_cache(maxsize=4)
def _build_client(
    endpoint_url: str, region: str, access_key_id: str, secret_access_key: str
):
    """자격증명 조합당 boto3 S3 client 1회 생성(재사용). client 는 thread-safe.

    설정은 lru_cache get_settings 싱글톤에서 오므로 자격증명 튜플로 캐시한다 —
    매 요청마다 service 모델 로딩 비용을 반복하지 않는다.
    """
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def make_client(settings: Settings):
    """R2 용 boto3 S3 client. 자격증명·endpoint 를 명시 전달하고 SigV4 를 고정한다."""
    _ensure_enabled(settings)
    return _build_client(
        settings.r2_endpoint_url,
        settings.r2_region,
        settings.r2_access_key_id,
        settings.r2_secret_access_key,
    )


def build_temp_key(user_id, ext: str) -> str:
    """서버 생성 업로드 스테이징 key — `temp/{user_id}/{uuid}.{ext}`.

    ext 는 확장자(점 없는 'xlsx' 형태). 라우터가 화이트리스트 검증 후 점 제거해 넘긴다.
    """
    return f"{TEMP_PREFIX}/{user_id}/{uuid4()}.{ext}"


def promote_key(temp_key: str, dest_prefix: str = STATEMENT_PREFIX) -> str:
    """temp 스테이징 key → 정식 보관 key. `temp/{rest}` → `{dest_prefix}/{rest}`.

    dest_prefix 기본값은 broker_statement(기존 호출 보존). bug_report 첨부는
    BUG_REPORT_PREFIX 를 넘긴다. user_id·uuid·ext 는 그대로 보존(추적성). 라우터가
    이미 temp prefix 를 검증하지만 방어적으로 한 번 더 확인한다.
    """
    prefix = f"{TEMP_PREFIX}/"
    if not temp_key.startswith(prefix):
        raise APIError(ERR_UPLOAD_MISSING, 400)
    return f"{dest_prefix}/{temp_key[len(prefix):]}"


def copy_object(settings: Settings, src_key: str, dst_key: str) -> None:
    """서버측 copy(temp → 정식). 동기 네트워크 호출 — async 에선 threadpool 로 감쌀 것.

    소스 부재(업로드 미완료 상태로 submit) → APIError(400). content-type 은 기본
    MetadataDirective=COPY 로 보존되어 어드민 다운로드 GET 이 그대로 동작한다.
    """
    client = make_client(settings)
    try:
        client.copy_object(
            Bucket=settings.r2_bucket,
            Key=dst_key,
            CopySource={"Bucket": settings.r2_bucket, "Key": src_key},
        )
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in ("NoSuchKey", "404", "NotFound"):
            raise APIError(ERR_UPLOAD_MISSING, 400) from exc
        raise


def delete_object(settings: Settings, key: str) -> None:
    """best-effort 삭제(DB 실패 시 정식 객체 보상 삭제용). 실패는 무시한다.

    동기 네트워크 호출 — async 에선 threadpool 로 감쌀 것.
    """
    try:
        make_client(settings).delete_object(Bucket=settings.r2_bucket, Key=key)
    except Exception:
        pass


def generate_put_url(settings: Settings, storage_key: str, content_type: str) -> str:
    """presigned PUT URL. Content-Type 을 서명에 고정한다 — 클라이언트 PUT 의
    Content-Type 헤더가 이 값과 정확히 일치해야 서명이 유효하다(불일치 시 R2 가 거부)."""
    client = make_client(settings)
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket,
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.r2_presign_expiry,
    )


def generate_get_url(
    settings: Settings, storage_key: str, *, filename: str, bucket: str | None = None
) -> str:
    """presigned GET URL(어드민 다운로드). ResponseContentDisposition 으로 원본
    파일명 첨부 다운로드를 강제한다.

    filename 은 사용자 제어(파일피커) — 한글·따옴표가 들어가도 안전하도록 RFC 5987
    `filename*=UTF-8''<percent-encoded>` 로 인코딩한다(raw 삽입 시 헤더 깨짐/파일명 garble).
    bucket 은 행별 저장값을 우선 사용(버킷 마이그레이션 후에도 옛 객체 다운로드 유지),
    없으면 현재 설정 버킷.
    """
    client = make_client(settings)
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket or settings.r2_bucket,
            "Key": storage_key,
            "ResponseContentDisposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
        ExpiresIn=settings.r2_presign_expiry,
    )
