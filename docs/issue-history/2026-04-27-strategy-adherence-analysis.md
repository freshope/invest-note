# Spec: 전략 계획/실제 분리 및 분석 정합성 개선

> Completed: 2026-04-27

## Background / Problem

분석 탭은 전략별 성과를 SELL의 `strategy_type` 기준으로 집계한다. 그러나 BUY 전략은 진입 계획이고 SELL 시점의 실제 보유일과 다를 수 있어, 전략별 승률·손익·보유일 지표가 왜곡될 수 있다.

## Goals

- SELL 분석에서 계획 전략과 보유일 기반 실제 전략을 분리한다.
- SELL 저장/재계산 시점에 FIFO로 매칭된 BUY 계획 전략과 보유일을 확정 저장한다.
- 분석/요약 조회 시점에는 저장된 SELL `strategy_type`과 `holding_days`로 지표를 산출한다.
- 분석 탭에 전략 준수율과 준수/이탈별 성과를 표시한다.
- 기존 거래 등록/수정 흐름은 손익금액과 같은 재계산 경로로 파생값 정합성을 유지한다.

## Design

### Approach

- FIFO lot 소비 기준으로 SELL별 계획 전략과 보유일을 산출해 `strategy_type`, `holding_days`에 저장한다.
- 여러 BUY 전략이 섞이면 소비 수량이 가장 큰 전략을 대표 계획 전략으로 사용하고, 동률이면 먼저 소비된 lot의 전략을 사용한다.
- 실제 전략은 보유일 기준으로 자동 산출한다: 1일 이하 `SCALPING`, 30일 이하 `SWING`, 그 외 `LONG_TERM`.
- 계획 전략이 없거나 `UNKNOWN`이면 준수 상태는 `UNKNOWN`, 같으면 `FOLLOWED`, 다르면 `DEVIATED`.
- `holding_days` 컬럼을 추가하고 기존 SELL 거래는 마이그레이션/백필로 채운다.
- 분석/프로필/거래 요약은 보유일 FIFO fallback을 조회 시점에 수행하지 않고 저장값을 사용한다.
- `strategy_evaluation`은 별도 저장하지 않고 `strategy_type + holding_days`로 단순 계산한다.

### Primary Files

- `api/src/invest_note_api/domain/analysis/strategy_adherence.py` - SELL별 계획/실제/준수 평가 공통 유틸 추가
- `api/src/invest_note_api/domain/analysis/aggregate.py` - 전략 집계 기준과 준수 집계 확장
- `api/src/invest_note_api/domain/realized_pnl.py` - 손익/평단/보유일/계획 전략 계산 단일 경로 확장
- `api/src/invest_note_api/db_ops/pnl_sync.py` - SELL 파생값 일괄 갱신
- `api/src/invest_note_api/routers/analysis.py` - 신규 분석 응답 필드 노출
- `api/src/invest_note_api/routers/trades.py` - 거래 요약의 전략 평가 산식을 분석과 동일하게 교체
- `app/src/lib/api-client.ts` / `app/src/lib/analysis/aggregate.ts` - 신규 응답 타입 반영
- `app/src/components/analysis/*` - 계획 전략별 성과 문구와 전략 준수 지표 표시
- `supabase/migrations/011_add_holding_days.sql` - `holding_days` 컬럼 추가 및 기존 SELL 백필

## Implementation Checklist

- [x] 백엔드 전략 계획/실제/준수 평가 유틸 추가
- [x] 분석 summary 집계와 거래 summary API를 공통 유틸 기준으로 변경
- [x] 백엔드 테스트 추가/수정
- [x] 프론트 타입과 분석 탭 표시 반영
- [x] SELL `holding_days` 저장 컬럼 추가 및 마이그레이션/백필 반영
- [x] SELL `strategy_type`을 손익 재계산 경로에서 BUY 계획 전략으로 갱신
- [x] 타입 체크 passes (`pnpm -C app exec tsc --noEmit`)
- [x] 백엔드 테스트 passes (`cd api && poetry run pytest -q`)

## Risks / Open Questions

- 부분 매도에서 여러 BUY 전략이 섞이는 경우 대표 전략 1개로 귀속한다. 손익을 전략별 비례 배분하는 고정밀 방식은 후속 개선으로 남긴다.
- `compute_holding_days_map`은 저장값 전환 후 compatibility map 역할만 남아 있어 후속 정리 대상으로 백로그에 남긴다.
