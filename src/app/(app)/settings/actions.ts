"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import { signOut as authSignOut } from "@/app/auth/actions";

export async function signOut(): Promise<void> {
  await authSignOut();
}

type ActionState = { error?: string; success?: boolean } | undefined;

const MAX_NAME_LENGTH = 50;
const MAX_BROKER_LENGTH = 50;
const MAX_CASH_BALANCE = 9999999999999999.99; // numeric(18,2) 최대값

function parseCashBalance(raw: string | null): number | null {
  if (!raw || raw.trim() === "") return 0;
  const num = Number(raw.replace(/,/g, ""));
  if (isNaN(num)) return null;
  if (num < 0) return null;
  if (num > MAX_CASH_BALANCE) return null;
  return num;
}

export async function createAccount(
  _state: ActionState,
  formData: FormData
): Promise<ActionState> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: "로그인이 필요합니다." };
  }

  const name = (formData.get("name") as string)?.trim();
  const broker = (formData.get("broker") as string)?.trim() || null;
  const rawCashBalance = formData.get("cash_balance") as string;

  if (!name) return { error: "계좌명을 입력해주세요." };
  if (name.length > MAX_NAME_LENGTH) return { error: `계좌명은 ${MAX_NAME_LENGTH}자 이하로 입력해주세요.` };
  if (broker && broker.length > MAX_BROKER_LENGTH) return { error: `증권사명은 ${MAX_BROKER_LENGTH}자 이하로 입력해주세요.` };

  const cashBalance = parseCashBalance(rawCashBalance);
  if (cashBalance === null) return { error: "올바른 예수금 금액을 입력해주세요." };

  const { error } = await supabase
    .from("accounts")
    .insert({
      user_id: user.id,
      name,
      broker: broker || null,
      cash_balance: cashBalance,
    });

  if (error) {
    return { error: "계좌를 추가할 수 없습니다. 다시 시도해주세요." };
  }

  revalidatePath("/settings");
  return { success: true };
}

export async function updateAccount(
  _state: ActionState,
  formData: FormData
): Promise<ActionState> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: "로그인이 필요합니다." };
  }

  const id = formData.get("id") as string;
  const name = (formData.get("name") as string)?.trim();
  const broker = (formData.get("broker") as string)?.trim() || null;
  const rawCashBalance = formData.get("cash_balance") as string;

  if (!id) return { error: "계좌 정보가 올바르지 않습니다." };
  if (!name) return { error: "계좌명을 입력해주세요." };
  if (name.length > MAX_NAME_LENGTH) return { error: `계좌명은 ${MAX_NAME_LENGTH}자 이하로 입력해주세요.` };
  if (broker && broker.length > MAX_BROKER_LENGTH) return { error: `증권사명은 ${MAX_BROKER_LENGTH}자 이하로 입력해주세요.` };

  const cashBalance = parseCashBalance(rawCashBalance);
  if (cashBalance === null) return { error: "올바른 예수금 금액을 입력해주세요." };

  const { error } = await supabase
    .from("accounts")
    .update({ name, broker: broker || null, cash_balance: cashBalance })
    .eq("id", id)
    .eq("user_id", user.id);

  if (error) {
    return { error: "계좌를 수정할 수 없습니다. 다시 시도해주세요." };
  }

  revalidatePath("/settings");
  return { success: true };
}

export async function deleteAccount(
  _state: ActionState,
  formData: FormData
): Promise<ActionState> {
  const supabase = await createClient();
  const { data: { user }, error: authError } = await supabase.auth.getUser();

  if (authError || !user) {
    return { error: "로그인이 필요합니다." };
  }

  const id = formData.get("id") as string;
  if (!id) return { error: "계좌 정보가 올바르지 않습니다." };

  // 거래 기록이 있는 계좌는 삭제 불가
  const { count, error: countError } = await supabase
    .from("trades")
    .select("id", { count: "exact", head: true })
    .eq("account_id", id)
    .eq("user_id", user.id);

  if (countError) {
    return { error: "계좌 정보를 확인할 수 없습니다." };
  }

  if (count && count > 0) {
    return { error: "거래 기록이 있는 계좌는 삭제할 수 없습니다." };
  }

  const { error } = await supabase
    .from("accounts")
    .delete()
    .eq("id", id)
    .eq("user_id", user.id);

  if (error) {
    return { error: "계좌를 삭제할 수 없습니다. 다시 시도해주세요." };
  }

  revalidatePath("/settings");
  return { success: true };
}
