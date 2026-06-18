"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  adminApi,
  type NpsUnmatchedRow,
  type NpsUnmatchedUpdateInput,
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

function npsKey(row: NpsUnmatchedRow) {
  return { nps_name: row.nps_name, nps_as_of: row.nps_as_of };
}

function EditDialog({ row }: { row: NpsUnmatchedRow }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const [holdingLevel, setHoldingLevel] = useState(row.holding_level ?? "");
  const [resolvedTicker, setResolvedTicker] = useState(
    row.resolved_ticker ?? "",
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (input: NpsUnmatchedUpdateInput) =>
      adminApi.npsUnmatched.update(npsKey(row), input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "nps-unmatched"] });
      setOpen(false);
    },
    onError: (e) =>
      setErrorMsg(e instanceof ApiError ? e.message : "수정에 실패했습니다."),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    mutation.mutate({
      // holding_level 은 NOT NULL 컬럼 — 빈값이면 키를 생략(undefined)해 미갱신.
      // null 전송 시 NULL UPDATE 로 제약 위반(500). resolved_ticker 는 의도적 해제(null) 허용.
      holding_level: holdingLevel || undefined,
      resolved_ticker: resolvedTicker || null,
    });
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
          <DialogTitle>NPS 항목 수정 · {row.nps_name}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="edit_holding_level">보유 수준 (holding_level)</Label>
            <Input
              id="edit_holding_level"
              value={holdingLevel}
              onChange={(e) => setHoldingLevel(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="edit_resolved_ticker">해소 티커 (resolved_ticker)</Label>
            <Input
              id="edit_resolved_ticker"
              value={resolvedTicker}
              onChange={(e) => setResolvedTicker(e.target.value)}
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
              {mutation.isPending ? "저장 중..." : "저장"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteButton({ row }: { row: NpsUnmatchedRow }) {
  const [open, setOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => adminApi.npsUnmatched.remove(npsKey(row)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "nps-unmatched"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
      setOpen(false);
    },
    onError: (e) =>
      setErrorMsg(e instanceof ApiError ? e.message : "삭제에 실패했습니다."),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          삭제
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>삭제 확인</DialogTitle>
        </DialogHeader>
        <p className="text-[14px] text-muted-foreground">
          &quot;{row.nps_name}&quot; ({row.nps_as_of}) 항목을 삭제할까요?
        </p>
        {errorMsg && <p className="text-[13px] text-destructive">{errorMsg}</p>}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              취소
            </Button>
          </DialogClose>
          <Button
            variant="destructive"
            disabled={mutation.isPending}
            onClick={() => {
              setErrorMsg(null);
              mutation.mutate();
            }}
          >
            삭제
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function NpsRowActions({ row }: { row: NpsUnmatchedRow }) {
  return (
    <div className="flex justify-end gap-2">
      <EditDialog row={row} />
      <DeleteButton row={row} />
    </div>
  );
}
