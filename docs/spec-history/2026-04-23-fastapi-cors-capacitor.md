# Spec: FastAPI CORS — Capacitor WebView origin 허용

> 완료: 2026-04-23

## 배경 / 문제

Capacitor 래핑 후 iOS/Android 앱에서 홈 데이터가 미로딩됨. 원인은 FastAPI의 CORS 허용 목록에 Capacitor WebView origin(iOS `capacitor://localhost`, Android `https://localhost`)이 빠져 있기 때문.

현재 `api/src/invest_note_api/config.py`의 `cors_origins` 기본값은 `["http://localhost:3000", "https://localhost:3000"]`뿐이고, production에서도 `NEXT_PUBLIC_API_BASE_URL` 대응 프론트 호스트만 허용됨.

## 목표

- iOS 실기기 앱(Capacitor)에서 홈 데이터 API 호출이 CORS 오류 없이 성공한다.
- Android 실기기 앱(Capacitor)에서 홈 데이터 API 호출이 CORS 오류 없이 성공한다.
- 기존 웹(`http://localhost:3000`, production 프론트) 호출은 영향 없음.
- production 배포 시 `CORS_ORIGINS` 환경변수 갱신 안내가 문서화된다.

## 설계

### 접근 방식

`settings.cors_origins`의 기본값과 `.env.example`에 Capacitor WebView origin 두 개(`capacitor://localhost`, `https://localhost`)를 추가. `CORSMiddleware` 호출부(`api/src/invest_note_api/main.py:31-37`)는 이미 `settings.cors_origins`를 참조하므로 설정만 바꾸면 자동 반영. `allow_credentials=True`, 고정 리스트, `allow_origin_regex` 미사용 유지.

### 주요 변경 파일

- `api/src/invest_note_api/config.py` — `cors_origins` 기본값에 `"capacitor://localhost"`, `"https://localhost"` 추가 (포트 없는 origin).
- `api/.env.example` — `CORS_ORIGINS` 예시 JSON 배열에 동일 origin 추가.
- `api/tests/test_cors.py` (신규) — 허용 origin(Capacitor 2개 + 웹 1개)은 preflight 통과, 비허용 origin은 차단됨을 검증. `tests/conftest.py`의 `_make_app` 패턴 재사용.

## 구현 체크리스트

- [x] `api/src/invest_note_api/config.py` — `cors_origins` 기본값에 Capacitor origin 2개 추가
- [x] `api/.env.example` — `CORS_ORIGINS` 예시에 Capacitor origin 2개 추가
- [x] `api/tests/test_cors.py` 신규 작성 — 허용/차단 origin 각각 검증
- [x] `pytest tests/test_cors.py -v` 통과 확인 (전체 149 passed)
- [x] production 배포용 `CORS_ORIGINS` 갱신 안내를 `docs/decisions.md`에 남김

## 우려사항 / 리스크

- **production 환경변수 미반영 시 여전히 실패**: 코드 기본값 변경만으로는 부족. 배포 환경변수 갱신을 별도 액션으로 포함.
- **`https://localhost` vs `https://localhost:3000`**: 포트 유무로 별개 origin이므로 둘 다 유지 필요.
- **`allow_credentials=True` 제약**: 와일드카드 금지 — 고정 리스트이므로 문제없음.
