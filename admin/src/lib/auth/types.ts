// Provider-neutral auth 타입. 컴포넌트·lib/api·페이지는 이 타입만 사용하고,
// 외부 auth SDK 의 User 타입은 절대 import 하지 않는다(격리 경계).
// auth provider 교체 시 lib/auth/ 구현만 교체하면 이 인터페이스는 그대로 유지된다.

export interface AdminUser {
  id: string;
  email: string | null;
}

export type AuthChangeCallback = (user: AdminUser | null) => void;
