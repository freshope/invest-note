import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { jsonError } from "@/lib/api-server/errors";

export async function POST(req: NextRequest) {
  try {
    const { email, password } = await req.json();

    if (!email || !password) {
      return jsonError("이메일과 비밀번호를 입력해주세요.", 400);
    }

    const supabase = await createClient();
    const { error } = await supabase.auth.signUp({
      email: String(email).trim(),
      password: String(password),
    });

    if (error) return jsonError(error.message, 400);
    return NextResponse.json({ success: true, message: "가입 확인 이메일을 발송했습니다. 이메일을 확인해주세요." });
  } catch {
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
