// Provider-neutral auth 타입. 컴포넌트·lib/api·페이지는 이 타입만 사용한다.
// auth 구현(lib/auth/index)이 바뀌어도 이 인터페이스는 그대로 유지된다.

export interface AuthUser {
  id: string;
  email: string | null;
}

export type AuthChangeCallback = (user: AuthUser | null) => void;
