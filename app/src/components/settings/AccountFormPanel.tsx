"use client";

import { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  FullScreenPanelFooter,
} from "@/components/base/FullScreenPanel";
import { accountsApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { BROKERS } from "@/lib/brokers";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { VALIDATION_LIMITS } from "@/lib/constants/validation";
import { fmtNumberInput, formatNumberInput, parseNumberInput } from "@/lib/format";
import type { Account } from "@/types/database";

const schema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "계좌명을 입력해주세요.")
    .max(VALIDATION_LIMITS.ACCOUNT_NAME_MAX),
  broker: z.string().nullable(),
  cash_display: z.string(),
});

type FormValues = z.infer<typeof schema>;

interface AccountFormPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  account?: Account;
}

export function AccountFormPanel({ open, onOpenChange, account }: AccountFormPanelProps) {
  const isEdit = !!account;
  const queryClient = useQueryClient();

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    setValue,
    setError,
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: account?.name ?? "",
      broker: account?.broker ?? null,
      cash_display: fmtNumberInput(account?.cash_balance ? Number(account.cash_balance) : null),
    },
  });

  // open=true 또는 account prop이 바뀔 때 폼 갱신.
  // 항상 마운트 상태이므로 재오픈 시 더티 상태·에러가 남지 않도록 open 기준으로 reset.
  useEffect(() => {
    if (!open) return;
    reset({
      name: account?.name ?? "",
      broker: account?.broker ?? null,
      cash_display: fmtNumberInput(account?.cash_balance ? Number(account.cash_balance) : null),
    });
  }, [open, account, reset]);

  const broker = watch("broker");

  async function onSubmit(values: FormValues) {
    const input = {
      name: values.name,
      broker: values.broker || null,
      cash_balance: parseNumberInput(values.cash_display),
    };
    try {
      if (isEdit) {
        await accountsApi.update(account!.id, input);
      } else {
        await accountsApi.create(input);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
        queryClient.invalidateQueries({ queryKey: queryKeys.accounts }),
      ]);
      onOpenChange(false);
    } catch (err) {
      setError("root", { message: err instanceof Error ? err.message : "저장에 실패했습니다." });
    }
  }

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title={isEdit ? "계좌 수정" : "계좌 추가"} />
        <FullScreenPanelBody>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col min-h-full">
            <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="name">
                  계좌명 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  placeholder="예: 키움증권 위탁계좌"
                  maxLength={VALIDATION_LIMITS.ACCOUNT_NAME_MAX}
                  {...register("name")}
                />
                {errors.name && (
                  <p className="text-sm text-destructive">{errors.name.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label>증권사</Label>
                <div className="grid grid-cols-3 gap-2">
                  {BROKERS.map((b) => {
                    const isSelected = broker === b.name;
                    return (
                      <button
                        key={b.name}
                        type="button"
                        onClick={() => setValue("broker", isSelected ? null : b.name)}
                        className={cn(
                          "flex flex-col items-center gap-1.5 rounded-xl border p-3 text-center transition-colors",
                          isSelected
                            ? "border-primary bg-primary/5 ring-2 ring-primary ring-offset-1"
                            : "border-border hover:bg-muted/50"
                        )}
                      >
                        <BrokerLogo broker={b.name} size={36} />
                        <span className="text-xs leading-tight text-foreground">{b.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="cash_display">예수금 (원)</Label>
                <Controller
                  control={control}
                  name="cash_display"
                  render={({ field }) => (
                    <Input
                      id="cash_display"
                      type="text"
                      inputMode="numeric"
                      placeholder="0"
                      value={field.value}
                      onChange={(e) => field.onChange(formatNumberInput(e.target.value))}
                    />
                  )}
                />
              </div>
            </div>

            <FullScreenPanelFooter>
              {errors.root && (
                <p className="mb-2 text-sm text-destructive">{errors.root.message}</p>
              )}
              <Button type="submit" size="xl" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "저장 중..." : isEdit ? "수정하기" : "추가하기"}
              </Button>
            </FullScreenPanelFooter>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
