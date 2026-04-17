import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const {
    data: { user },
    error: getUserError,
  } = await supabase.auth.getUser();

  // API 라우트는 자체 auth 검사(requireUser)를 수행 — 세션 쿠키만 갱신 후 리다이렉트 없이 반환
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return supabaseResponse;
  }

  // Supabase 장애 시 보호된 페이지 경로만 차단
  if (getUserError) {
    const { pathname } = request.nextUrl;
    if (pathname !== "/login" && !pathname.startsWith("/auth/")) {
      const url = request.nextUrl.clone();
      url.pathname = "/login";
      return NextResponse.redirect(url);
    }
    return supabaseResponse;
  }

  const { pathname } = request.nextUrl;

  // 인증 필요 경로에 비로그인 접근 시 로그인 페이지로 리다이렉트
  // /auth/ 경로는 제외 (이메일 인증 콜백 등)
  if (!user && pathname !== "/login" && !pathname.startsWith("/auth/")) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // 로그인 상태에서 로그인 페이지 접근 시 홈으로 리다이렉트
  if (user && pathname === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
