// ⚠️ BE `BE_DEEPLINK_SCHEME`(기본 app.pixelwave.investnote://auth/callback)와 정합 유지 필수.
// 이 두 값이 조합한 `{scheme}://{host}/callback` 로 BE 가 일회용 code 를 돌려보낸다 —
// 한쪽만 바꾸면 네이티브 콜백이 유실된다.
export const NATIVE_URL_SCHEME = "app.pixelwave.investnote";
export const NATIVE_CALLBACK_HOST = "auth";
