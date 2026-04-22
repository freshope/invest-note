import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { AccountUpdateSchema } from "@/lib/api-server/validators";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const parsed = AccountUpdateSchema.safeParse(await req.json());
    if (!parsed.success) {
      return jsonError(parsed.error.issues[0]?.message ?? "올바르지 않은 입력입니다.", 400);
    }

    if (Object.keys(parsed.data).length === 0) return new NextResponse(null, { status: 204 });

    const { data, error } = await supabase
      .from("accounts")
      .update(parsed.data)
      .eq("id", id)
      .eq("user_id", user.id)
      .select("*")
      .single();

    if (error || !data) return jsonError("계좌를 수정할 수 없습니다. 다시 시도해주세요.", 500);
    return NextResponse.json(data);
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const { count, error: countError } = await supabase
      .from("trades")
      .select("id", { count: "exact", head: true })
      .eq("account_id", id)
      .eq("user_id", user.id);

    if (countError) return jsonError("계좌 정보를 확인할 수 없습니다.", 500);
    if (count && count > 0)
      return jsonError("거래 기록이 있는 계좌는 삭제할 수 없습니다.", 409);

    const { error } = await supabase
      .from("accounts")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("계좌를 삭제할 수 없습니다. 다시 시도해주세요.", 500);
    return new NextResponse(null, { status: 204 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
