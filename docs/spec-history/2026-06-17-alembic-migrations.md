# Spec: Alembic 도입 (마이그레이션 도구 교체)

> 완료: 2026-06-17

## Context / 배경

DB 종속성 제거 작업(2026-06-16 decisions.md)의 **Phase 2 = 도구 교체**다. 포터블 RLS(033~036)로 스키마를 표준 PostgreSQL 객체로 옮겼고, 실제 DB lift-and-shift(self-hosted PG 컨테이너 `invest-note-db` :64340)는 **이미 완료되어 모니터링 중**이다. 남은 것은 마이그레이션 **도구**를 supabase CLI(`supabase db push`) → Alembic 으로 교체하는 일이다.

ORM이 없으므로(순수 asyncpg + raw SQL) Alembic은 **SQLAlchemy 모델/autogenerate 없이 raw SQL 러너**로만 쓴다. 목표는 supabase 의존 도구를 떼어내고, 어떤 표준 Postgres 에서도 동일하게 도는 마이그레이션 흐름을 갖는 것이다. Supabase 는 Auth(GoTrue) 전용으로만 남는다.

## 목표 (완료 기준)

- `cd api && poetry run alembic upgrade head` 가 **빈 DB에 전체 스키마를 생성**한다(라이브와 동등).
- 기존 운영/개발 DB는 `alembic stamp` 로 baseline 표시되어 `upgrade head` 가 **no-op("already at head")** 이다.
- 새 마이그레이션은 `alembic revision` → `upgrade()` 에 `op.execute(raw SQL)` 흐름으로 작성된다.
- supabase CLI 의 public 스키마 마이그레이션은 비활성화되고, 로컬도 Alembic 이 스키마를 소유한다(단일 소유, drift 없음).
- 기존 단위 테스트(`pytest -q`)는 FakePool 기반이라 무영향으로 통과한다.

## 설계

### 핵심 결정

| 항목 | 결정 |
|---|---|
| 위치 | `api/alembic.ini` + `api/alembic/{env.py, versions/}` (api Poetry 프로젝트 내부) |
| 드라이버 | **psycopg v3 동기** (`postgresql+psycopg://`). async 템플릿/ORM 모델/autogenerate 미사용 |
| 의존성 | `alembic`, `psycopg[binary]` 를 `[tool.poetry.dependencies]` **main** 에 추가(prod/CI 가 upgrade 실행) |
| 마이그레이션 URL | 신규 env `MIGRATION_DATABASE_URL`(없으면 `DATABASE_URL` fallback). **direct 5432 + superuser(`postgres`)** — 앱 role `invest_note_app`(NOSUPERUSER)은 `pg_trgm` extension/`drop role` 권한 없음 |
| baseline | 라이브 스키마 `pg_dump --schema-only` 스냅샷 → 단일 baseline 리비전. 기존 DB는 `stamp`, 신규 DB는 baseline 으로 전체 생성 |
| baseline 시점 | **036(app_authenticated drop) cleanup 적용 후** 스냅샷 → role 없는 단일 clean baseline (036 시퀀싱 함정 원천 제거) |
| supabase/migrations | `supabase/migrations_archive/` 로 git mv(history 보존). `[db.migrations] enabled=false` |
| 운영 마이그레이션 실행 | 호스트 포트 미publish → `docker exec` 수동 ops 단계. **Dockerfile/배포 자동화는 이번 범위 밖**(추후) — surgical 유지 |

### env.py 요지

```python
def _migration_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

target_metadata = None  # raw SQL 러너, autogenerate 미사용
# online: engine_from_config 에 _migration_url() 주입, transaction_per_migration
```

### baseline 리비전 요지

`upgrade()` 가 co-located `baseline_schema.sql`(pg_dump 산출물)을 읽어 `op.get_bind().exec_driver_sql(sql_text)` **1회** 실행. `;` 단위 split 금지(plpgsql `$$` 본문 깨짐). `downgrade()` = `raise NotImplementedError`.

⚠️ **PG 18 pg_dump 는 `\restrict`/`\unrestrict` psql 메타커맨드를 emit** → `exec_driver_sql` 이 `syntax error at or near "\"` 로 깨진다(2026-06-17 실증). 로드 시 `^\` 줄을 제거한 뒤 실행한다:

```python
from pathlib import Path
from alembic import op

def upgrade() -> None:
    sql = (Path(__file__).resolve().parent.parent / "baseline_schema.sql").read_text()
    # PG 18 pg_dump 의 psql 전용 메타커맨드(\restrict/\unrestrict) 제거 — 엔진 연결 적용이라 안전
    sql = "\n".join(l for l in sql.splitlines() if not l.startswith("\\"))
    op.get_bind().exec_driver_sql(sql)

def downgrade() -> None:
    raise NotImplementedError("baseline 은 되돌리지 않는다")
```

### 주요 변경 파일

- `api/pyproject.toml` — alembic + psycopg[binary] main deps
- `api/alembic.ini` (신규) — `script_location = alembic`, url 은 env.py 주입
- `api/alembic/env.py` (신규) — URL 주입·scheme rewrite, `target_metadata=None`
- `api/alembic/script.py.mako` (신규) — 표준 템플릿
- `api/alembic/versions/0001_baseline.py` (신규) — pg_dump 스냅샷 러너
- `api/alembic/baseline_schema.sql` (신규) — 라이브 스키마 덤프
- `supabase/config.toml` — `[db.migrations] enabled=false`
- `api/.env.example`, `api/.env.production` — `MIGRATION_DATABASE_URL` 가이드
- `api/Makefile` — `migrate`, `migrate-new` 타깃
- `.github/workflows/ci-api.yml` — `migrate-verify` job(빈 PG → upgrade → pg_dump diff empty)
- `docs/decisions.md` — 결정 로그 항목, `docs/backlog.md` — 036 항목 갱신, `AGENTS.md` — 마이그레이션 작성 흐름 갱신

## 구현 체크리스트

**Phase 1 — scaffold (DB 불필요, 지금 가능)** ✅ 완료
- [x] `api/pyproject.toml` 에 `alembic`, `psycopg[binary]` 추가 → `poetry lock && poetry install` → `poetry run alembic --version`(1.18.4)
- [x] `api/alembic.ini` 작성 (script_location, file_template 날짜prefix)
- [x] `api/alembic/env.py` 작성 (MIGRATION_DATABASE_URL fallback + `.env.local` 최소 파싱 + scheme rewrite, target_metadata=None)
- [x] `api/alembic/script.py.mako` (op.execute 가이드) + `api/alembic/versions/.gitkeep`

**Phase 2 — 설정 디커플 (DB 불필요)** ✅ 완료 (supabase start public-empty 확인은 로컬 스택 기동 시 검증)
- [x] `supabase/config.toml` `[db.migrations] enabled=false`
- [x] `api/.env.example` + `api/.env.production` 에 `MIGRATION_DATABASE_URL` 가이드 추가
- [x] `api/Makefile` 에 `migrate`(`alembic upgrade head`), `migrate-new name=...`(`alembic revision -m`) 타깃 추가

**Phase 3 — CI & 문서 (DB 불필요)** ✅ 완료
- [x] `.github/workflows/ci-api.yml` 에 `migrate-verify` job 추가(postgres:18 service → role 부트스트랩 → `alembic upgrade head` 성공 + 핵심 테이블 존재). pg_dump-diff 는 순환·취약이라 미채택(이유는 decisions.md)
- [x] `docs/decisions.md` 결정 로그 + `docs/backlog.md` 036 항목 + `api/README.md` 마이그레이션 섹션 갱신 (AGENTS.md 는 마이그레이션 워크플로 섹션 부재 → README 가 적정 위치)

**Phase 4 — baseline & stamp** ✅ dev/코드 완료 (prod 적용만 사용자 잔여)
- [x] 036 을 dev :64340 에 적용(DROP OWNED/ROLE) + 미사용 `DB_APP_ROLE` 상수 제거 → `pg_dump --schema-only` 로 `api/alembic/baseline_schema.sql` 생성(`app_authenticated` 0건, `pg_trgm`·`$$`·`OWNER TO invest_note_app` 존재)
- [x] `api/alembic/versions/0001_baseline.py` 작성(exec_driver_sql + `^\` strip + search_path 복원) → fresh postgres:18 에 `alembic upgrade head` 성공(12 테이블·pg_trgm·version=0001_baseline)
- [x] dev·prod 양쪽 stamp 완료(2026-06-17). prod = 036 적용(drop owned 는 `invest_note` DB 컨텍스트 필수 — 그게 per-DB라 다른 DB 접속 시 drop role 이 "objects depend" 로 막힘) → drift diff(타입/함수 owner 무해 차이만) → psql 로 `alembic_version` stamp. dev = `0001_baseline (head)`
- [x] `supabase/migrations/*.sql`(36개) → `supabase/migrations_archive/` git mv

**Phase 5 — 검증** ✅ 완료
- [x] fresh DB: role 부트스트랩 → `alembic upgrade head` → 12 테이블·trades·pg_trgm 생성(baseline 은 라이브 dev 에서 떠 동등)
- [x] 기존 DB: 재실행 시 "Running upgrade" 없음(= already at head) 무변경
- [x] 새 마이그레이션 smoke: `alembic revision` → `down_revision='0001_baseline'` 체인 확인(throwaway 제거)
- [x] `poetry run pytest -q` 640 passed + ruff clean (DB_APP_ROLE 제거 무영향)
- [x] `cd api && poetry run pytest -q` 녹색 (FakePool 무영향)

## 우려사항 / 리스크

- **036 시퀀싱**: baseline 은 036 적용 **후** 떠야 clean(role 없음). 그래서 Phase 4 는 cleanup 에 의존(Phase 1~3 은 먼저 진행 가능). 대안(지금 baseline + 036 을 Alembic rev 0002)은 fresh DB 에 role 부트스트랩→drop 이 필요해 더 복잡 → 채택 안 함.
- **fresh DB role 선행**: pg_dump 는 role 을 안 싣지만 `OWNER TO invest_note_app` 는 싣는다 → CI/fresh 볼륨은 upgrade **전** `invest_note_app` 역할 생성 필요(baseline 밖 부트스트랩 step). "alembic=스키마, role=별도" 소유 분리.
- **FakePool 맹점**: 단위 테스트는 SQL 미실행이라 마이그레이션이 깨져도 통과 → CI `migrate-verify` job(실 PG diff)이 유일한 실검증 게이트.
- **운영 실행 컨텍스트**: 호스트 포트 미publish → 랩탑 TCP 불가, `docker exec`/one-shot 컨테이너 필요(memory `project_prod_db_access`). 운영 DB 명령은 에이전트가 실행하지 않고 사용자에게 제시.

## 운영(prod) 잔여 런북 — 사용자 실행 (호스트 포트 미publish → VPS SSH + `docker exec`, superuser)

> ⚠️ **stamp 는 "prod 스키마 == baseline" 을 신뢰하는 행위다.** 033 expand/034 contract/035 FORCE/036 가
> 단계·게이트로 적용돼 prod 가 dev 덤프와 byte-identical 인지 미확인 → stamp **전** drift 검증 필수.

1. **선행:** Phase 2(api-v1.3.0 SET ROLE 제거) 운영 베이킹 무이상 확인(RLS 에러·0행 민원 없음).
2. **036 적용** (prod DB 컨테이너에서):
   ```bash
   docker exec -i <prod_db> psql -U postgres -d invest_note -v ON_ERROR_STOP=1 \
     -c "drop owned by app_authenticated; drop role app_authenticated;"
   ```
3. **drift 검증 (stamp 전 게이트 — empty 여야 진행):**
   ```bash
   diff <(grep -v '^\\' api/alembic/baseline_schema.sql) \
        <(docker exec <prod_db> pg_dump --schema-only -U postgres -d invest_note | grep -v '^\\')
   ```
   empty → 4 진행. non-empty → 실 drift, 조사 후 진행(절대 그냥 stamp 금지).
4. **stamp** (alembic 파일이 prod 컨테이너엔 없음 → psql 로 직접; alembic stamp 와 동치):
   ```bash
   docker exec <prod_db> psql -U postgres -d invest_note -v ON_ERROR_STOP=1 -c \
     "CREATE TABLE IF NOT EXISTS public.alembic_version (version_num varchar(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)); INSERT INTO public.alembic_version (version_num) VALUES ('0001_baseline');"
   ```
   검증: `SELECT version_num FROM alembic_version;` → `0001_baseline`.

## 검증 (end-to-end)

1. 로컬: `docker compose down -v && up` → `invest_note_app` role 부트스트랩 → `cd api && poetry run alembic upgrade head` → `pg_dump --schema-only` 가 baseline 과 diff empty.
2. CI `migrate-verify` job 녹색.
3. `cd api && poetry run pytest -q` 녹색.
