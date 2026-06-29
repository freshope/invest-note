export const NATIVE_URL_SCHEME = "app.pixelwave.investnote";
export const NATIVE_CALLBACK_HOST = "auth";

// 웹 BE flow 콜백 라우트(개발 편의용). BE 가 `client=web` 로그인 후 일회용 code 를
// 이 경로로 302 redirect 한다 — BE env `be_app_web_redirect_url` 의 path 와 일치해야 한다
// (예: http://localhost:3000/auth/callback). FE 는 BE 에 redirect 를 전송하지 않으므로
// (BE env 가 출처) 이 상수는 라우트 문서값이다.
export const WEB_CALLBACK_PATH = "/auth/callback/";
