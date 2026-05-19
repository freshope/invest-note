# Spec: Apple App Review 대응 — 계정 탈퇴 추가 & 로그아웃 안정화

> 완료: 2026-05-20

## 배경 / 문제

Apple App Review (Submission ID f16491c8-02d4-4ab4-ad32-4422491e7366, 2026-05-19) 에서 두 건의 피드백을 받음.

1. **Guideline 5.1.1(v)** — 계정 생성 기능이 있으면 계정 삭제 기능도 반드시 제공해야 함. 현재 앱에는 탈퇴 기능 없음 → 리젝 사유.
2. **Guideline 2.1(a)** — 리뷰어가 iPhone 17 Pro Max / iOS 26.5 에서 "Unable to sign out" 보고. 개발자 환경에서는 재현 불가지만 코드 분석 결과 `handleSignOut` 의 에러 처리·redirect 의존성이 취약하여 특정 환경에서 실패할 여지가 있음.

## 목표

- 설정 화면에 "회원 탈퇴" 섹션이 추가되어 있고, 버튼을 누르면 destructive 경고 다이얼로그가 뜬다.
- 다이얼로그에서 확정하면 BE `DELETE /api/me` 가 호출되어 Supabase Auth 사용자 + 모든 데이터(accounts, trades 등)가 삭제되고, 클라이언트는 자동 로그아웃 후 `/login` 으로 이동한다.
- 로그아웃 버튼이 어떤 네트워크/저장소 상태에서도 항상 `/login` 으로 이동하며, 실패 시 사용자가 인지할 수 있다 (toast).
- BE 회귀 테스트 + FE 타입 체크 통과.

## 설계

### 1) 계정 탈퇴

**BE**
- `be/src/invest_note_api/routers/me.py` 에 `DELETE /api/me` 추가.
- Supabase Admin API (`SUPABASE_SECRET_KEY` — Supabase 신규 키 형식 `sb_secret_...`) 로 `${SUPABASE_URL}/auth/v1/admin/users/{user_id}` 에 `DELETE` 호출. `auth.users` row 삭제 시 `accounts/trades` 는 FK `on delete cascade` 로 자동 정리됨 (`supabase/migrations/001_initial_schema.sql`).
- Service role key 가 없으면 503 ("계정 삭제 기능이 비활성화되었습니다"). 외부 호출 실패 시 502.

**FE**
- `fe/src/components/settings/DeleteAccountSection.tsx` 신규 — destructive 버튼 + Dialog 경고.
- `fe/src/lib/api-client.ts` 에 `usersApi.deleteAccount` 추가.
- `fe/src/app/(app)/settings/page.tsx` 에 새 "계정" 섹션 마운트.
- 탈퇴 성공 시 `supabase.auth.signOut({ scope: "local" })` + `queryClient.clear()` + `router.replace("/login")`.

### 2) 로그아웃 안정화

`fe/src/components/settings/UserInfoSection.tsx` 의 `handleSignOut` 을 다음과 같이 강건하게 수정.

```ts
async function handleSignOut() {
  setPending(true);
  const supabase = createClient();
  try {
    await supabase.auth.signOut({ scope: "local" });
  } catch (error) {
    console.error("[signOut]", error);
    toast.error("로그아웃 중 문제가 발생했어요. 다시 시도해주세요.");
  } finally {
    queryClient.clear();
    router.replace("/login");
    setPending(false);
  }
}
```

- `scope: "local"` — 서버 호출 실패에도 클라이언트 토큰만 비움 (iOS WKWebView storage / 네트워크 단절 회피).
- `finally` 에서 `queryClient.clear()` + `router.replace("/login")` 강제 → AuthGuard 의존 제거.
- 에러는 `console.error` + sonner toast 로 가시화.

### 주요 변경 파일

- `be/src/invest_note_api/routers/me.py` — `DELETE /api/me` 추가
- `be/src/invest_note_api/config.py` — `supabase_secret_key` 설정 추가
- `be/.env.example` — `SUPABASE_SECRET_KEY` 키 추가
- `be/tests/test_me.py` — DELETE 엔드포인트 테스트
- `fe/src/lib/api-client.ts` — `usersApi.deleteAccount`
- `fe/src/components/settings/DeleteAccountSection.tsx` — 신규
- `fe/src/components/settings/UserInfoSection.tsx` — 로그아웃 로직 개선
- `fe/src/app/(app)/settings/page.tsx` — 새 섹션 마운트

## 구현 체크리스트

- [x] BE: `Settings` 에 `supabase_secret_key` 추가 + `.env.example` 업데이트
- [x] BE: `routers/me.py` 에 `DELETE /api/me` 구현 (Supabase admin API 호출 + 에러 매핑)
- [x] BE: `tests/test_me.py` 에 삭제 케이스 추가
- [x] BE: `cd be && poetry run pytest -q` 통과
- [x] FE: `usersApi.deleteAccount` 추가
- [x] FE: `DeleteAccountSection` 컴포넌트 작성
- [x] FE: `settings/page.tsx` 에 섹션 마운트
- [x] FE: `UserInfoSection.handleSignOut` 개선
- [x] FE: `pnpm -C fe exec tsc --noEmit` 통과
- [x] 수동: 로그아웃·탈퇴 흐름 검증

## 우려사항 / 리스크

- **Service role key 운영 보관**: 배포 환경 (Render/Fly 등) secret 등록 필수. 키 누락 시 탈퇴 503.
- **재현 불가 로그아웃 버그**: `scope:"local"` + `finally redirect` 로 어떤 경로에서도 클라이언트 세션이 비워지고 `/login` 으로 이동하도록 강제.
- **Apple 재심사 증빙**: 데모 계정 (pixelwave.reviewer@gmail.com) 으로 탈퇴 후 `be/scripts/seed_demo_data.py` 재시드 필요. 재제출 시 App Store Connect Notes 에 탈퇴 경로 명시.
- **CASCADE 누락 가드**: 새 user-scoped 테이블 추가 시 `on delete cascade` 누락하면 탈퇴 실패.
