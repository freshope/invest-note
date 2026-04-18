import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { TradeUpdateSchema } from "@/lib/api-server/validators";
import type { Trade } from "@/types/database";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const { data, error } = await supabase
      .from("trades")
      .select("*, accounts(name, broker)")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (error || !data) return jsonError("거래를 찾을 수 없습니다.", 404);

    const { accounts: acc, ...trade } = data as Trade & {
      accounts: { name: string; broker: string | null } | null;
    };
    return NextResponse.json({ ...trade, account: acc ?? undefined });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;

    const body = await req.json();
    const parsed = TradeUpdateSchema.safeParse(body);
    if (!parsed.success) {
      return jsonError(parsed.error.issues[0]?.message ?? "올바르지 않은 입력입니다.", 400);
    }

    // 소유 확인
    const { data: existing, error: fetchError } = await supabase
      .from("trades")
      .select("id")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (fetchError || !existing) return jsonError("거래를 찾을 수 없습니다.", 404);

    const { account_id, ...rest } = parsed.data;
    const patch: Record<string, unknown> = { ...rest };

    // account_id는 소유권 DB 검증 필요
    if (account_id !== undefined) {
      const { count } = await supabase
        .from("accounts")
        .select("id", { count: "exact", head: true })
        .eq("id", account_id)
        .eq("user_id", user.id);
      if (!count) return jsonError("올바른 계좌를 선택해주세요.", 400);
      patch.account_id = account_id;
    }

    if (Object.keys(patch).length === 0) return new NextResponse(null, { status: 204 });

    const { error } = await supabase
      .from("trades")
      .update(patch)
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("저장할 수 없습니다. 다시 시도해주세요.", 500);
    return new NextResponse(null, { status: 204 });
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

    const { error } = await supabase
      .from("trades")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("삭제할 수 없습니다. 다시 시도해주세요.", 500);
    return new NextResponse(null, { status: 204 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
