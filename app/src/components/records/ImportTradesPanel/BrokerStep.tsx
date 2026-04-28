"use client";

import { CheckCircle2Icon, AlertCircleIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/base/Select";
import { BROKER_OPTIONS } from "./brokers";

interface Props {
  detectedBrokerKey: string | null;
  selectedBrokerKey: string | null;
  onSelect: (key: string) => void;
  onNext: () => void;
}

export function BrokerStep({ detectedBrokerKey, selectedBrokerKey, onSelect, onNext }: Props) {
  const detected = BROKER_OPTIONS.find((b) => b.key === detectedBrokerKey);

  return (
    <div className="flex flex-col gap-6">
      {detected ? (
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
          <CheckCircle2Icon className="h-5 w-5 shrink-0 text-green-600 dark:text-green-400" />
          <div>
            <p className="text-sm font-medium text-green-800 dark:text-green-200">
              증권사 자동 감지됨
            </p>
            <p className="text-sm text-green-700 dark:text-green-300">{detected.label}</p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-800 dark:bg-yellow-950">
          <AlertCircleIcon className="mt-0.5 h-5 w-5 shrink-0 text-yellow-600 dark:text-yellow-400" />
          <div>
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              증권사를 자동으로 감지하지 못했습니다
            </p>
            <p className="text-sm text-yellow-700 dark:text-yellow-300">
              아래에서 증권사를 직접 선택해주세요.
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-foreground">증권사</label>
        <Select
          value={selectedBrokerKey ?? detectedBrokerKey ?? ""}
          onValueChange={(v) => onSelect(v as string)}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="증권사 선택" />
          </SelectTrigger>
          <SelectContent>
            {BROKER_OPTIONS.map((b) => (
              <SelectItem key={b.key} value={b.key}>
                {b.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        onClick={onNext}
        disabled={!selectedBrokerKey && !detectedBrokerKey}
        className="self-end"
      >
        다음
      </Button>
    </div>
  );
}
