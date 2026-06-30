export const AUTH_ERROR_CODE = {
  OAUTH_FAILED: "oauth_failed",
} as const;

export type AuthErrorCode = (typeof AUTH_ERROR_CODE)[keyof typeof AUTH_ERROR_CODE];

export const LOGIN_OAUTH_FAILED_PATH_WITH_SLASH = `/login/?error=${AUTH_ERROR_CODE.OAUTH_FAILED}` as const;
