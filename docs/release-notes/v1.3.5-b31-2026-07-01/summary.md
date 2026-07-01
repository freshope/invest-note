# 출시 노트 요약 — v1.3.5_31

> 작성일: 2026-07-01
> 비교 기준: app-v1.3.4_31 (2026-06-30)
> 대상 빌드: v1.3.5_31 (준비 중 · release/app-v1.3.5_31 브랜치, bump 커밋 완료)
> 배포 형태: **OTA web-only (빌드 번호 31 유지, 스토어 재심사 불필요)** — 스토어 노트 생략(store-notes:skip)

## Git 로그 (app-v1.3.4_31..HEAD, --no-merges)

| 해시 | 날짜 | 메시지 |
|------|------|--------|
| c709fdb | 2026-07-01 | chore: bump version app-v1.3.5_31 |
| dda1d89 | 2026-07-01 | docs: spec-current → spec-history/2026-07-01-holding-today-change.md 이동 |
| d1f1ea7 | 2026-07-01 | feat: 보유종목 카드에 오늘(전일 종가 대비) 등락 표시 |
| 443bd90 | 2026-07-01 | test(api): import/commit 실DB 통합 테스트 |
| fa93dac | 2026-07-01 | test(api): RLS 제거 후속 — 라우터 인라인 user_id 필터 HTTP 격리 가드 |
| 95be21d | 2026-06-30 | docs(backlog): 해외주식 지원 트랙 종결 |
| e357e59 | 2026-06-30 | feat: name_ko 표시 확장 — 분석 탭 집중도 + 종목 상세 헤더 한글화 |
| 65c9ab1 | 2026-06-30 | docs(backlog): 배포/인프라 트랙 종결 |
| d8e42dc | 2026-06-30 | docs: KIS 연동 트랙 종결 |
| 940c5f4 | 2026-06-30 | docs(readme): 프로젝트 소개 README 작성 |
| 2e6ffea | 2026-06-30 | refactor(api): legacy /api·bare alias 제거, /v1 단일화 |
| a62650f | 2026-06-30 | fix(board): popup ack post_id 키잉 + 방어 필터 + 중복 제거 |
| 474193a | 2026-06-30 | test(import): /import/preview·/import/commit HTTP 테스트 추가 |
| 70ab036 | 2026-06-30 | feat(import): 업로드 파일 확장자 ↔ 증권사 형식 불일치 검증 |
| e67e15a | 2026-06-30 | chore(lint): _-prefix 미사용 var 무시 설정 |
| c62f6d4 | 2026-06-30 | feat(board): my-posts 페이지네이션 + unread-summary 분리 |
| f6a5219 | 2026-06-30 | feat(notices): 공지 목록 페이지네이션("더 보기") + queryKey 분리 |
| a965963 | 2026-06-30 | docs(backlog): '미지원 계좌 전체 안내' 항목 삭제 |
| 5b7bd3e | 2026-06-30 | fix(lint): admin eslint config 추가 + set-state-in-effect 정식 해결 |
| 0eda20f | 2026-06-30 | test(import): BROKERS↔BROKER_OPTIONS 라벨 동기화 회귀 가드 |
| d5c5ab0 | 2026-06-30 | docs: README curl 예시 /api → /v1 경로 갱신 |

## 동기간 spec-history 항목

- 2026-06-30-board-list-unify.md — 게시판 목록 통합: 내 글/공지 페이지네이션 + unread-summary 분리
- 2026-07-01-holding-today-change.md — 보유종목 카드에 오늘(전일 종가 대비) 등락 표시

## 분류표

| 라벨 | 항목 | 출시 노트 반영 |
|------|------|--------------|
| NEW | 보유종목 카드에 오늘(전일 종가 대비) 등락 표시 (d1f1ea7) | ✓ (다음 네이티브 제출 시) |
| IMPROVE | 해외 종목 한글 표시명 확장 — 분석 탭 집중도 + 종목 상세 헤더 (e357e59) | ✓ |
| IMPROVE | 게시판 내 글 목록 페이지네이션 + 안읽음 요약 분리 (c62f6d4) | ✓ |
| IMPROVE | 공지 목록 "더 보기" 페이지네이션 (f6a5219) | ✓ |
| IMPROVE | 일괄등록 파일 확장자 ↔ 증권사 형식 불일치 검증 (70ab036) | ✓ |
| FIX | 게시판 팝업 ack post_id 키잉 + 방어 필터 + 중복 제거 (a62650f) | ✓ |
| INTERNAL | legacy /api·bare alias 제거, /v1 단일화 (2e6ffea) | ✗ (MIN 1.3.0 floor 로 커버됨) |
| INTERNAL | admin eslint config + set-state-in-effect 해결 (5b7bd3e) | ✗ |
| INTERNAL | api/app/import 테스트 다수 추가·lint 정리·docs·backlog 그루밍 | ✗ |

집계: NEW 1 · IMPROVE 4 · FIX 1 · INTERNAL 다수

> 스토어 노트는 생성하지 않음(OTA web-only). 위 NEW/IMPROVE/FIX 항목은 **다음 네이티브 제출 때** `release-notes ... since app-v1.3.0_31`(마지막 네이티브 태그) 로 묶어 스토어 노트로 작성한다.

## 검증 결과

- app-store-ko.md: 해당 없음 (store-notes:skip)
- play-store-ko.md: 해당 없음 (store-notes:skip)
- 대상 버전 1.3.5 / build 31 — package.json·iOS·Android 3곳 일치 (make version-check 통과), 폴더명·summary 일치
- 마이그레이션 파일: 없음 (api/alembic/versions/ diff 비어 있음)

## 배포 체크리스트 (출시 노트 외 운영 작업 — 실행 순서대로)

1. **DB 마이그레이션: 불필요** — `app-v1.3.4_31..HEAD` 에 신규/수정 마이그레이션 파일 없음 (api/alembic/versions/ 무변경).
2. **BE 배포: 필요 (api + admin 둘 다)**
   - api: board_repo.py(페이지네이션), external/quotes.py, main.py(/v1 단일화), routers/board·analysis, schemas/board 등 런타임 변경 → **api 재배포 필요**.
   - admin: AuthProvider.tsx, lib/auth/index.ts 런타임 변경 → **admin 재배포 필요**.
   - main push 시 Coolify 가 자동 배포. 마이그레이션이 없으므로 순서 제약은 없음.
3. **MIN_SUPPORTED_VERSION: 현재 `1.3.0`** — **변경 불필요 (판단은 사용자)**.
   - 이번 창의 유일한 잠재적 breaking 은 `legacy /api·bare alias 제거`(2e6ffea)인데, 해당 제거의 하위호환 floor 가 이미 1.3.0 이고 현재 MIN 이 1.3.0 이라 스토어 라이브(≥1.3.0) 앱은 전부 /v1 을 사용 → 추가 인상 근거 없음.
   - board/notices 변경은 additive(페이지네이션 파라미터 추가)로 구버전 앱 하위호환.
4. **모바일 스토어 제출: 불필요** — OTA web-only 빌드. OTA 번들 배포로 반영, 빌드 번호 31 유지. 누적 NEW/IMPROVE/FIX 는 다음 네이티브 제출 때 스토어 노트로 묶여 나감.

**실행 순서**: (마이그레이션 없음) → api·admin BE 배포(main push = Coolify 자동) → OTA 번들 배포(app web-only). 스토어 제출 없음.

## 다음 빌드를 위한 메모

- 이번은 native build 31 위의 5번째 OTA(v1.3.1~1.3.5). 다음 **네이티브 제출** 시 `since app-v1.3.0_31` 로 release-notes 를 돌려 v1.3.1~1.3.x OTA 누적 변경(오늘 등락 표시·한글 표시명 확장·게시판/공지 페이지네이션·일괄등록 검증·팝업 버그 수정 등)을 한 번에 스토어 노트로 작성.
- `legacy /api·bare alias 제거`가 라이브에 나가면, 혹시 남아 있는 1.2.x 이하 구버전 앱은 API 접근 불가 — 현재 MIN=1.3.0 게이트가 이미 차단하므로 실사용 영향 없음(강제 업데이트로 유도). 배포 후 실제 트래픽에서 /api·bare 호출 잔존 여부 모니터링 권장.
