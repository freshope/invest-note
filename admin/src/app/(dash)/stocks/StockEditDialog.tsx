"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type StockRow, type StockUpdateInput, ApiError } from "@/lib/api";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/base/Dialog";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { fmtText } from "@/lib/format";

// stocks 편집 화이트리스트(BE StockUpdate 와 정합). seed 가 덮어쓰는 필드는 제외됨.
const EDIT_FIELDS: { key: keyof StockUpdateInput; label: string }[] = [
  { key: "asset_name", label: "종목명" },
  { key: "market", label: "시장(market)" },
  { key: "exchange", label: "거래소(exchange)" },
  { key: "sector", label: "섹터(sector)" },
  { key: "currency", label: "통화(currency)" },
  { key: "us_index", label: "US 지수(us_index)" },
];

export function StockEditDialog({ row }: { row: StockRow }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  // 초기값 — string 필드만 폼으로 노출. is_active 는 별도 토글.
  const [form, setForm] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      EDIT_FIELDS.map((f) => [
        f.key,
        row[f.key] == null ? "" : String(row[f.key]),
      ]),
    ),
  );
  const [isActive, setIsActive] = useState<boolean>(
    row.is_active !== false,
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (input: StockUpdateInput) =>
      adminApi.stocks.update(
        { country_code: row.country_code, ticker: row.ticker },
        input,
      ),
    onSuccess: () => {
      // stocks 목록 전체(모든 page/q 변형) invalidate.
      queryClient.invalidateQueries({ queryKey: ["admin", "stocks"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
      setOpen(false);
    },
    onError: (e) => {
      setErrorMsg(
        e instanceof ApiError ? e.message : "수정에 실패했습니다.",
      );
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    // 빈 문자열 → null(nullable 필드), 변경분만 의미. 전부 전송해도 화이트리스트라 안전.
    const input: StockUpdateInput = {
      asset_name: form.asset_name || undefined,
      market: form.market || undefined,
      exchange: form.exchange || null,
      sector: form.sector || null,
      currency: form.currency || undefined,
      us_index: form.us_index || null,
      is_active: isActive,
    };
    mutation.mutate(input);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          수정
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            종목 수정 · {fmtText(row.country_code)}/{fmtText(row.ticker)}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          {EDIT_FIELDS.map((f) => (
            <div key={f.key} className="space-y-1">
              <Label htmlFor={f.key}>{f.label}</Label>
              <Input
                id={f.key}
                value={form[f.key] ?? ""}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, [f.key]: e.target.value }))
                }
              />
            </div>
          ))}
          <label className="flex items-center gap-2 text-[14px]">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            활성(is_active)
          </label>

          {errorMsg && (
            <p className="text-[13px] text-destructive">{errorMsg}</p>
          )}

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                취소
              </Button>
            </DialogClose>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "저장 중..." : "저장"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
