import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const { count, error } = await supabase
      .from("trades")
      .select("id", { count: "exact", head: true })
      .eq("account_id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("거래 수를 확인할 수 없습니다.", 500);
    return NextResponse.json({ count: count ?? 0 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
