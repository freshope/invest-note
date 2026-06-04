"""자산 변화 페이지 응답 스키마 — CamelModel(camelCase 직렬화)."""
from __future__ import annotations

from invest_note_api.schemas._base import CamelModel


class AssetHistoryResponse(CamelModel):
    """GET /assets/history 응답.

    - series: 차트 점(날짜 오름차순). 계좌뷰/종목뷰 동일 — {date, value}.
    - items: 목록(최신 먼저). 계좌뷰 {date, value, change} / 종목뷰 +{close, qty}.
    - incomplete: 일부 종목 fetch 실패/carry-forward 불가로 결측 가능 시 true(부분 표시 배지).
    - asOf: 마지막 점 기준시각(오늘 점은 라이브 시세). camelCase(NOT as_of).

    자산 = 보유 종목 평가액(현금 잔고 제외).
    """

    series: list[dict]
    items: list[dict]
    incomplete: bool
    as_of: str
