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
} from "@/components/base/FullScreenPanel";
import { accountsApi } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { Account } from "@/types/database";

const BROKERS = [
  { name: "키움증권", short: "키움", color: "bg-orange-500" },
  { name: "미래에셋증권", short: "미래", color: "bg-blue-600" },
  { name: "NH투자증권", short: "NH", color: "bg-green-600" },
  { name: "삼성증권", short: "삼성", color: "bg-blue-800" },
  { name: "KB증권", short: "KB", color: "bg-amber-500" },
  { name: "한국투자증권", short: "한투", color: "bg-sky-600" },
  { name: "대신증권", short: "대신", color: "bg-red-600" },
  { name: "신한투자증권", short: "신한", color: "bg-indigo-500" },
  { name: "메리츠증권", short: "메리츠", color: "bg-teal-600" },
  { name: "하나증권", short: "하나", color: "bg-emerald-500" },
  { name: "토스증권", short: "토스", color: "bg-blue-500" },
];

const schema = z.object({
  name: z.string().trim().min(1, "계좌명을 입력해주세요.").max(50),
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
    formState: { isSubmitting, errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: account?.name ?? "",
      broker: account?.broker ?? null,
      cash_display: account?.cash_balance ? Number(account.cash_balance).toLocaleString("ko-KR") : "",
    },
  });

  useEffect(() => {
    reset({
      name: account?.name ?? "",
      broker: account?.broker ?? null,
      cash_display: account?.cash_balance ? Number(account.cash_balance).toLocaleString("ko-KR") : "",
    });
  }, [account, reset]);

  const broker = watch("broker");

  async function onSubmit(values: FormValues) {
    const cash = values.cash_display.replace(/,/g, "");
    const input = {
      name: values.name,
      broker: values.broker || null,
      cash_balance: cash ? Number(cash) : 0,
    };
    if (isEdit) {
      await accountsApi.update(account!.id, input);
    } else {
      await accountsApi.create(input);
    }
    await queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    onOpenChange(false);
    reset({ name: "", broker: null, cash_display: "" });
  }

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent open={open}>
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
                  maxLength={50}
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
                        <span className={cn("flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold text-white", b.color)}>
                          {b.short}
                        </span>
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
                      onChange={(e) => {
                        const digits = e.target.value.replace(/[^0-9]/g, "");
                        field.onChange(digits ? Number(digits).toLocaleString("ko-KR") : "");
                      }}
                    />
                  )}
                />
              </div>
            </div>

            <div
              className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
              style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
            >
              <Button type="submit" size="xl" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "저장 중..." : isEdit ? "수정하기" : "추가하기"}
              </Button>
            </div>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
