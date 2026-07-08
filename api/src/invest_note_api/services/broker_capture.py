"""Stage 1 캡처 서비스 — 거래내역서 파일 → 파싱 → 원본 R2 보관 + 원장 적재.

일괄등록(Stage 2)과 **무관하게** 동작한다(다중 진입점: 일괄등록·admin·API·향후 auto-import).
원장(import_ledger_entries)이 임포트의 단일 소스가 되고, 물질화(trades 생성)는 Stage 2 가
원장을 읽어 수행한다. 이 서비스는 trades 를 건드리지 않는다.

멱등/dedup:
- 같은 파일 재업로드 → content_sha256 로 batch 통째 스킵(원장 재적재 안 함).
- 같은 거래 다른 파일 → 원장은 append(둘 다 보존). 중복 trade 방지는 물질화(Stage 2)가 담당.
- 원본 파일 저장은 best-effort(무손실 책임은 원장 raw) — R2 미설정/실패 시 storage_key=NULL 로 진행.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg
from starlette.concurrency import run_in_threadpool

from ..broker_import import PARSERS
from ..broker_import.base import ParseResult
from ..config import Settings
from ..db import acquire_for_user
from ..db_ops.import_ledger_repo import insert_batch, insert_ledger_entries
from ..domain.trade_import import parse_kst_date
from ..errors import APIError
from ..storage import r2

logger = logging.getLogger(__name__)

# broker_key → 원본 파일 확장자(R2 key 표기용).
_EXT_BY_BROKER = {
    "samsung_xlsx": "xlsx",
    "toss_pdf": "pdf",
    "shinhan_pdf": "pdf",
    "mirae_pdf": "pdf",
}


@dataclass
class CaptureResult:
    batch_id: str
    is_new_file: bool          # False = 같은 파일 재업로드(원장 재적재 안 함)
    row_count: int             # 원장에 반영된 전체 행 수(신규 파일일 때만 > 0)
    trade_row_count: int       # 그중 거래 인식 행 수
    parse_result: ParseResult  # Stage 2 preview 가 재사용(원장 재조회 없이 이어감)


def _upload_source_file(
    settings: Settings, key: str, file_bytes: bytes, content_type: str | None
) -> None:
    """원본 파일 R2 업로드(best-effort). 실패해도 진행 — 무손실 책임은 원장 raw.

    단, storage_key 는 이미 batch 에 박혀 있어 '있다고 광고'하므로, 실패를 조용히 삼키면
    ops 가 '90일 만료'와 '업로드 실패'를 구분할 수 없다 → warning 으로 남긴다(읽기는 404 관용).
    """
    try:
        r2.put_object(settings, key, file_bytes, content_type)
    except Exception:
        logger.warning("원장 원본 파일 R2 업로드 실패(key=%s) — 원장 raw 로 진행", key, exc_info=True)


async def capture_statement(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    user_id: UUID,
    broker_key: str,
    filename: str,
    content_type: str | None,
    file_bytes: bytes,
) -> CaptureResult:
    parser = PARSERS.get(broker_key)
    if parser is None:
        raise APIError(f"지원하지 않는 증권사입니다: {broker_key}", 400)

    # 동기 pdfplumber/openpyxl 파싱은 threadpool 로 — async 이벤트 루프 비차단.
    try:
        parse_result = await run_in_threadpool(parser.parse, file_bytes, filename)
    except Exception:
        # 선택 증권사와 파일 형식 불일치(xlsx 파서 ← PDF = BadZipFile 등) → 원인 안내 400.
        raise APIError(
            f"이 파일은 {parser.display_name} 거래내역서 형식이 아닌 것 같아요. "
            "선택한 증권사가 맞는지 확인해주세요.",
            400,
        )

    # 거래·계좌번호·에러·캡처행이 모두 비면 증권사 미스매치(정상 내역서는 최소 계좌번호 헤더가
    # 잡힘) — 원장/파일을 만들지 않고 안내한다(bogus 캡처 방지). rows[] 포함: 비거래 행만 있는
    # 정상 파일(예: 배당만 있는 기간)이 거짓 400 으로 거부되지 않도록 새 SoT 도 함께 본다.
    if (
        not parse_result.trades
        and not parse_result.rows
        and not parse_result.account_hint
        and not parse_result.errors
    ):
        raise APIError(
            f"이 파일에서 {parser.display_name} 거래내역을 찾지 못했어요. "
            "선택한 증권사가 맞는지 확인해주세요.",
            400,
        )

    # 날짜 오류(미래 일자·해석 불가)는 정상 데이터가 아니라 신뢰할 수 없는 파일 또는 파서 이상의
    # 신호다 — 일부 행만 걸러내지 않고 파일 전체를 거절한다(캡처/원장에 남기지 않음).
    today = datetime.now(timezone.utc).date()
    for pt in parse_result.trades:
        parsed_date = parse_kst_date(pt.traded_at_kst)
        if parsed_date is None:
            raise APIError(
                f"거래 일자를 해석할 수 없는 행이 있어요(예: {pt.traded_at_kst!r}). "
                "파일이 손상되었을 수 있으니 다시 내려받아 업로드해 주세요.",
                400,
            )
        if parsed_date > today:
            raise APIError(
                f"미래 일자({pt.traded_at_kst}) 거래가 포함돼 있어요. "
                "올바른 거래내역서 파일인지 확인해 주세요.",
                400,
            )

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    ext = _EXT_BY_BROKER.get(broker_key, "bin")
    # content-addressed key(멱등). 실제 R2 업로드는 신규 파일(is_new)일 때만 — sha256 batch
    # dedup 이후로 미뤄, 재업로드/재-preview 시 동일 파일을 다시 PUT 하는 낭비를 피한다.
    storage_key = (
        r2.build_import_source_key(user_id, sha256, ext) if settings.r2_enabled else None
    )

    async with acquire_for_user(pool, user_id) as conn:
        batch_id, is_new = await insert_batch(
            conn,
            batch_id=uuid4(),
            user_id=user_id,
            broker_key=broker_key,
            parser_version=parser.version,
            filename=filename,
            content_type=content_type,
            size_bytes=len(file_bytes),
            storage_key=storage_key,
            content_sha256=sha256,
            account_hint=parse_result.account_hint,
        )
        row_count = 0
        if is_new:
            row_count = await insert_ledger_entries(
                conn, batch_id=batch_id, user_id=user_id, rows=parse_result.rows
            )

    # 신규 파일일 때만 원본 R2 업로드(best-effort — 실패해도 무손실 책임은 원장 raw; storage_key
    # 는 콘텐츠 주소라 유효하고 읽기 경로는 만료/부재 404 를 관용).
    if is_new and storage_key is not None:
        await run_in_threadpool(
            _upload_source_file, settings, storage_key, file_bytes, content_type
        )

    trade_rows = sum(1 for r in parse_result.rows if r.kind == "trade")
    return CaptureResult(
        batch_id=str(batch_id),
        is_new_file=is_new,
        row_count=row_count,
        trade_row_count=trade_rows,
        parse_result=parse_result,
    )
