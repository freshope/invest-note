"""자산 변화 페이지 응답 스키마 — CamelModel(camelCase 직렬화)."""
from __future__ import annotations

from invest_note_api.schemas._base import CamelModel


class AssetHistoryResponse(CamelModel):
    """GET /assets/history 응답.

    - series: 차트 점(날짜 오름차순). 계좌뷰/종목뷰 동일 — {date, value}.
    - items: 목록(최신 먼저). 계좌뷰 {date, value, change} / 종목뷰 +{close, qty}.
    - incomplete: 일부 종목 fetch 실패/carry-forward 불가로 결측 가능 시 true(부분 표시 배지).
    - asOf: 마지막 점 기준시각(오늘 점은 라이브 시세). camelCase(NOT as_of).
    - investedAmount: 현재 보유분 매수 원금(cost_basis 합, 스코프 동일). 차트의
      손익 기준 가이드 라인. 거래 없음/보유 없음이면 None. KRW 단위(US 보유는 spot 환산).
    - usdkrw: KRW 환산에 쓴 USD/KRW spot 환율(1개, 일자별 historical 아님).
      None=환율 미상(해외 보유 환산 불가) 또는 해외 보유 없음. camelCase(usdkrw).
    - hasForeign: 스코프에 해외(비-KRW) 보유가 하나라도 있으면 true.
      FE 가 (hasForeign && usdkrw==null) 일 때 '환율 불가' 안내를 띄운다(D4). camelCase(hasForeign).

    자산 = 보유 종목 평가액(현금 잔고 제외). series/items value 는 KRW(US 는 spot 환산).
    """

    series: list[dict]
    items: list[dict]
    incomplete: bool
    as_of: str
    invested_amount: float | None = None
    usdkrw: float | None = None
    has_foreign: bool = False
