import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { jsonError } from "@/lib/api-server/errors";

export async function POST() {
  try {
    const supabase = await createClient();
    const { error } = await supabase.auth.signOut();
    if (error) return jsonError(error.message, 500);
    return NextResponse.json({ success: true });
  } catch {
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
