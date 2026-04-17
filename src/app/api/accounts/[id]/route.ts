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

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { supabase, user } = await requireUser();
    const { id } = await params;
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
      .update({ name, broker, cash_balance: cashBalance })
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
