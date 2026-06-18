"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  adminApi,
  type NpsUnmatchedCreateInput,
  ApiError,
} from "@/lib/api";
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

// nps_unmatched 생성. PK(nps_name, nps_as_of) + NOT NULL holding_level 필수.
export function NpsCreateDialog() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    nps_name: "",
    nps_as_of: "",
    holding_level: "",
    resolved_ticker: "",
  });
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (input: NpsUnmatchedCreateInput) =>
      adminApi.npsUnmatched.create(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "nps-unmatched"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
      setOpen(false);
      setForm({ nps_name: "", nps_as_of: "", holding_level: "", resolved_ticker: "" });
    },
    onError: (e) => {
      setErrorMsg(e instanceof ApiError ? e.message : "생성에 실패했습니다.");
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    mutation.mutate({
      nps_name: form.nps_name,
      nps_as_of: form.nps_as_of,
      holding_level: form.holding_level,
      resolved_ticker: form.resolved_ticker || null,
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">신규 추가</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>NPS 항목 추가</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="nps_name">NPS 명칭 (nps_name)</Label>
            <Input
              id="nps_name"
              required
              value={form.nps_name}
              onChange={(e) =>
                setForm((p) => ({ ...p, nps_name: e.target.value }))
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="nps_as_of">기준일 (nps_as_of)</Label>
            <Input
              id="nps_as_of"
              type="date"
              required
              value={form.nps_as_of}
              onChange={(e) =>
                setForm((p) => ({ ...p, nps_as_of: e.target.value }))
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="holding_level">보유 수준 (holding_level)</Label>
            <Input
              id="holding_level"
              required
              value={form.holding_level}
              onChange={(e) =>
                setForm((p) => ({ ...p, holding_level: e.target.value }))
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="resolved_ticker">해소 티커 (resolved_ticker)</Label>
            <Input
              id="resolved_ticker"
              value={form.resolved_ticker}
              onChange={(e) =>
                setForm((p) => ({ ...p, resolved_ticker: e.target.value }))
              }
            />
          </div>

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
              {mutation.isPending ? "생성 중..." : "생성"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
