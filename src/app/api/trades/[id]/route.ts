import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/api-server/auth";
import { jsonError, HttpError } from "@/lib/api-server/errors";
import { TradeUpdateSchema } from "@/lib/api-server/validators";
import { recalcGroupPnL, tradeToGroupKey } from "@/lib/api-server/pnl-sync";
import { validateMutation } from "@/lib/analysis/realized-pnl";
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

// P&L 재계산이 필요한 필드 변경 여부 확인
// account_id/ticker/country는 수정 불가 필드이므로 제외
const PNL_AFFECTING_FIELDS = new Set(["price", "quantity", "trade_type", "commission", "tax"]);

function hasPnLAffectingChange(patch: Record<string, unknown>): boolean {
  return Object.keys(patch).some((k) => PNL_AFFECTING_FIELDS.has(k));
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

    // 소유 확인 + 기존 거래 전체 정보 조회 (검증용)
    const { data: existing, error: fetchError } = await supabase
      .from("trades")
      .select("*")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (fetchError || !existing) return jsonError("거래를 찾을 수 없습니다.", 404);

    const patch: Record<string, unknown> = Object.fromEntries(
      Object.entries(parsed.data).filter(([, v]) => v !== undefined)
    );

    if (Object.keys(patch).length === 0) return new NextResponse(null, { status: 204 });

    // P&L 영향 필드 변경 시 oversell 사전 검증 후 재계산
    if (hasPnLAffectingChange(patch)) {
      const { data: allTradesRaw } = await supabase
        .from("trades")
        .select("*")
        .eq("user_id", user.id);

      const allTrades = (allTradesRaw ?? []) as Trade[];
      const gKey = tradeToGroupKey(existing as Trade);

      const validation = validateMutation(allTrades, {
        type: "update",
        trade: existing as Trade,
        patch: patch as Partial<Trade>,
      });
      if (!validation.ok) return jsonError(validation.message, 400);

      const { error } = await supabase
        .from("trades")
        .update(patch)
        .eq("id", id)
        .eq("user_id", user.id);

      if (error) return jsonError("저장할 수 없습니다. 다시 시도해주세요.", 500);

      const { data: freshTrades } = await supabase.from("trades").select("*").eq("user_id", user.id);
      if (freshTrades) {
        await recalcGroupPnL(supabase, user.id, freshTrades as Trade[], gKey);
      }
    } else {
      const { error } = await supabase
        .from("trades")
        .update(patch)
        .eq("id", id)
        .eq("user_id", user.id);
      if (error) return jsonError("저장할 수 없습니다. 다시 시도해주세요.", 500);
    }

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

    // 삭제 대상 조회
    const { data: target, error: fetchError } = await supabase
      .from("trades")
      .select("*")
      .eq("id", id)
      .eq("user_id", user.id)
      .single();

    if (fetchError || !target) return jsonError("거래를 찾을 수 없습니다.", 404);

    // oversell 사전 검증
    const { data: allTradesRaw } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id);

    const allTrades = (allTradesRaw ?? []) as Trade[];
    const validation = validateMutation(allTrades, { type: "delete", trade: target as Trade });
    if (!validation.ok) {
      return jsonError(validation.message, 400);
    }

    const groupKey = tradeToGroupKey(target as Trade);

    const { error } = await supabase
      .from("trades")
      .delete()
      .eq("id", id)
      .eq("user_id", user.id);

    if (error) return jsonError("삭제할 수 없습니다. 다시 시도해주세요.", 500);

    // 삭제 후 그룹 재계산
    const { data: freshTrades } = await supabase.from("trades").select("*").eq("user_id", user.id);
    if (freshTrades) {
      await recalcGroupPnL(supabase, user.id, freshTrades as Trade[], groupKey);
    }

    return new NextResponse(null, { status: 204 });
  } catch (e) {
    if (e instanceof HttpError) return e.toResponse();
    return jsonError("서버 오류가 발생했습니다.", 500);
  }
}
