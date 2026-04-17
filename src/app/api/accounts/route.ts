import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";

const MAX_NAME_LENGTH = 50;
const MAX_BROKER_LENGTH = 50;
const MAX_CASH_BALANCE = 9999999999999999.99;

function parseCashBalance(raw: unknown): number | null {
  if (raw == null || raw === "") return 0;
  const num = Number(String(raw).replace(/,/g, ""));
  if (isNaN(num) || num < 0 || num > MAX_CASH_BALANCE) return null;
  return num;
}

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
    const body = await req.json();

    const name = String(body.name ?? "").trim();
    const broker = body.broker ? String(body.broker).trim() : null;
    const cashBalance = parseCashBalance(body.cash_balance);

    if (!name) return jsonError("계좌명을 입력해주세요.", 400);
    if (name.length > MAX_NAME_LENGTH)
      return jsonError(`계좌명은 ${MAX_NAME_LENGTH}자 이하로 입력해주세요.`, 400);
    if (broker && broker.length > MAX_BROKER_LENGTH)
      return jsonError(`증권사명은 ${MAX_BROKER_LENGTH}자 이하로 입력해주세요.`, 400);
    if (cashBalance === null)
      return jsonError("올바른 예수금 금액을 입력해주세요.", 400);

    const { data, error } = await supabase
      .from("accounts")
      .insert({ user_id: user.id, name, broker, cash_balance: cashBalance })
      .select("*")
      .single();

    if (error || !data) return jsonError("계좌를 추가할 수 없습니다. 다시 시도해주세요.", 500);
    return NextResponse.json(data, { status: 201 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
