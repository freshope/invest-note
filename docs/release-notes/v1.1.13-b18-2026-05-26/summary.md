# 출시 노트 요약 — v1.1.13_18

> 작성일: 2026-05-26
> 비교 기준: v1.1.12_17 (2026-05-23 태그)
> 대상 빌드: v1.1.13_18 (준비 중 — dirty tree 포함 초안, version-bump 4곳 미커밋)

## Git 로그 (v1.1.12_17..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| f4af888 | 2026-05-26 | chore(fe): remove unused icon and template assets |
| f950a27 | 2026-05-26 | chore(fe): convert PWA icons to webp and refresh app assets |
| 6b0476f | 2026-05-25 | chore(fe): regenerate app icons/splash assets and fix manifest MIME |
| 48c1f65 | 2026-05-24 | fix(fe): React 19 react-hooks 규칙 위반 lint 오류 정리 |
| e1f96dc | 2026-05-24 | fix: 알림 다이얼로그 버튼 크기·배치 개선 |
| bc96f8f | 2026-05-24 | docs: spec-current → spec-history/2026-05-24-trade-swipe-delete.md 이동 |
| be8e499 | 2026-05-24 | feat: 거래 카드 스와이프-삭제 도입 |
| 37da68d | 2026-05-24 | feat(settings): 버전 옆에 빌드 번호 표시 |
| f9a7055 | 2026-05-23 | fix(trades): bulk-delete 엣지 케이스 처리 |
| ac6933b | 2026-05-23 | docs: spec-current → spec-history/2026-05-23-trade-bulk-delete.md 이동 |
| ddacf5d | 2026-05-23 | feat: 기록 탭 거래 일괄 삭제 기능 추가 |
| 14f9ae7 | 2026-05-23 | docs: v1.1.12_17 출시 노트 추가 |
| e41c7fa | 2026-05-23 | chore: ignore obsidian vault and pnpm store |
| 711eb9c | 2026-05-23 | fix(be): portfolio summary accountId UUID 검증 + 응답 빌더 정리 |
| 3d3f1f2 | 2026-05-23 | fix(test): analysis 기간 필터 테스트를 동적 시각 기준으로 변경 |
| dc02bfe | 2026-05-23 | feat(be): KR 시세 fetch에 Yahoo Finance fallback 추가 |
| ea7fb44 | 2026-05-23 | fix: pull-to-refresh 시 시세 캐시 TTL 단축(60→10s) |
| 1df8c6c | 2026-05-23 | docs: spec-current → spec-history/2026-05-23-home-account-filter.md 이동 |
| 3d5369a | 2026-05-23 | feat: 메인 대시보드에 계좌 필터 추가 |

## 동기간 spec-history 항목

- `2026-05-24-trade-swipe-delete.md` — 거래 카드 좌측 스와이프 → 트레일링 삭제 버튼으로 단건 삭제 단축. 한 번에 한 카드만 열림, 선택 모드 시 비활성화.
- `2026-05-23-trade-bulk-delete.md` — 기록 탭 다중 선택 모드 + BE 트랜잭션 일괄 삭제 API(`POST /trades/bulk-delete`). 전체 선택/해제, oversell 충돌 안내.
- `2026-05-23-home-account-filter.md` — 메인 대시보드에 계좌 필터 칩 추가. BE `/portfolio/summary?accountId=` 로 KPI·차트·홀딩을 계좌 기준으로 좁힘.

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 거래 카드 스와이프-삭제 (be8e499, f9a7055 엣지케이스 흡수) | ✓ |
| NEW | 기록 탭 거래 일괄 삭제 / 선택 모드 (ddacf5d) | ✓ |
| NEW | 메인 대시보드 계좌 필터 (3d5369a) | ✓ |
| IMPROVE | 시세 표시 안정성·새로고침 정확도 (ea7fb44 TTL 60→10s + dc02bfe Yahoo fallback 묶음) | ✓ |
| IMPROVE | 알림 다이얼로그 버튼 크기·배치 (e1f96dc) | ✓ |
| IMPROVE | 설정 화면 버전 옆 빌드 번호 표시 (37da68d) | App Store만 1줄 / Play 제외 |
| INTERNAL | portfolio summary accountId UUID 검증·응답 빌더 정리 (711eb9c) | ✗ |
| INTERNAL | analysis 기간 필터 테스트 동적화 (3d3f1f2) | ✗ |
| INTERNAL | React 19 react-hooks lint 정리 (48c1f65) | ✗ |
| INTERNAL | 앱 아이콘/스플래시 재생성·webp 변환·manifest MIME·미사용 에셋 제거 (6b0476f, f950a27, f4af888) | ✗ |
| INTERNAL | obsidian vault / pnpm store gitignore (e41c7fa) | ✗ |
| INTERNAL | spec-history 이동·이전 출시 노트 문서 (bc96f8f, ac6933b, 1df8c6c, 14f9ae7) | ✗ |

## 검증 결과

- app-store-ko.md: 347자 / 4000자 한도 — 통과 (`LC_ALL=en_US.UTF-8 wc -m`)
- play-store-ko.md: 224자 / 500자 한도 — 통과 (`LC_ALL=en_US.UTF-8 wc -m`)
- 내부 식별자/커밋 해시/PR 번호 노출 없음 — 통과
- INTERNAL 항목이 스토어 본문에 섞이지 않음 — 통과
- 대상 버전(1.1.13 / 18)이 폴더명·summary 메타데이터·양쪽 노트와 일치 — 통과 (노트 본문에 버전 문자열 직접 노출은 없음)
- 톤: 이전 노트(v1.1.12_17) 격식체(`~했습니다.`)를 따름 — 통과

## 다음 빌드를 위한 메모

- **version bump 미커밋**: 4곳(`fe/package.json`, `be/pyproject.toml`, `android build.gradle`, `iOS project.pbxproj`)이 1.1.13/18로 bump됐으나 아직 커밋 전. release 브랜치에서 bump 커밋 + 본 노트 폴더를 같은 커밋/PR에 포함해야 함.
- `home-account-filter.md` 의 수동 검증 1건(계좌 2개 이상 환경에서 칩 전환·복귀·invalidate)이 미체크 상태 — 스토어 제출 전 실기기 확인 권장.
- `test_analysis_logic.py::test_1m_excludes_old` 의 hardcoded 날짜 결함은 3d3f1f2에서 동적화로 정리됨 (해소).
- 빌드 번호 표시(37da68d)는 지원 문의 대응용 마이너 개선이라 Play 노트에서 제외. 다음 빌드에서도 동일 기준 유지.
