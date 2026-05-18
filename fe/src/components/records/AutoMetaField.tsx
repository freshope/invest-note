"use client";

import type { ReactNode } from "react";
import { Label } from "@/components/base/Label";
import type { EmotionType, ReasoningTag } from "@/types/database";
import { EMOTION_LABELS, REASONING_TAG_LABELS } from "@/lib/constants/trading";

const AUTO_HINT = "(매수 시점에서 자동)";

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full bg-muted text-foreground text-[13px]">
      {children}
    </span>
  );
}

export function AutoEmotionField({ emotion }: { emotion: EmotionType | null }) {
  return (
    <div className="space-y-2">
      <Label>
        감정
        <span className="ml-1 text-[12px] font-normal text-muted-foreground">{AUTO_HINT}</span>
      </Label>
      {emotion ? (
        <Chip>{EMOTION_LABELS[emotion] ?? emotion}</Chip>
      ) : (
        <p className="text-[13px] text-muted-foreground">매수 시점의 감정으로 자동 설정됩니다.</p>
      )}
    </div>
  );
}

export function AutoReasoningTagsField({ tags }: { tags: ReasoningTag[] | null | undefined }) {
  const list = tags ?? [];
  return (
    <div className="space-y-2">
      <Label>
        분석 태그
        <span className="ml-1 text-[12px] font-normal text-muted-foreground">{AUTO_HINT}</span>
      </Label>
      {list.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {list.map((tag) => (
            <Chip key={tag}>{REASONING_TAG_LABELS[tag] ?? tag}</Chip>
          ))}
        </div>
      ) : (
        <p className="text-[13px] text-muted-foreground">매수 시점의 분석 태그로 자동 설정됩니다.</p>
      )}
    </div>
  );
}

export function AutoBuyReasonField({ reason }: { reason: string | null | undefined }) {
  const text = (reason ?? "").trim();
  return (
    <div className="space-y-2">
      <Label>
        매수 근거
        <span className="ml-1 text-[12px] font-normal text-muted-foreground">{AUTO_HINT}</span>
      </Label>
      {text ? (
        <p className="whitespace-pre-wrap rounded-md bg-muted px-3 py-2 text-[13px] text-foreground">
          {text}
        </p>
      ) : (
        <p className="text-[13px] text-muted-foreground">매수 시점의 매수 근거가 없습니다.</p>
      )}
    </div>
  );
}
