import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { AccountCreateSchema } from "@/lib/api-server/validators";

export async function GET() {
  try {
    const { supabase, user } = await requireUser();
    const [{ data: accounts, error }, { data: tradeCounts }] = await Promise.all([
      supabase
        .from("accounts")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: true }),
      supabase
        .from("trades")
        .select("account_id")
        .eq("user_id", user.id),
    ]);

    if (error) return jsonError("계좌 목록을 불러올 수 없습니다.", 500);

    const countMap: Record<string, number> = {};
    for (const t of tradeCounts ?? []) {
      countMap[t.account_id] = (countMap[t.account_id] ?? 0) + 1;
    }

    const result = (accounts ?? []).map((a) => ({
      ...a,
      cash_balance: Number(a.cash_balance),
      trade_count: countMap[a.id] ?? 0,
    }));

    return NextResponse.json(result);
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}

export async function POST(req: NextRequest) {
  try {
    const { supabase, user } = await requireUser();

    const parsed = AccountCreateSchema.safeParse(await req.json());
    if (!parsed.success) {
      return jsonError(parsed.error.issues[0]?.message ?? "올바르지 않은 입력입니다.", 400);
    }

    const { name, broker, cash_balance } = parsed.data;
    const { data, error } = await supabase
      .from("accounts")
      .insert({ user_id: user.id, name, broker, cash_balance })
      .select("*")
      .single();

    if (error || !data) return jsonError("계좌를 추가할 수 없습니다. 다시 시도해주세요.", 500);
    return NextResponse.json(data, { status: 201 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
