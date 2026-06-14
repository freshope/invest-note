"use client";

import { useState } from "react";
import { PlusIcon, XIcon } from "lucide-react";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";
import { Input } from "@/components/base/Input";
import { Button } from "@/components/base/Button";
import { Label } from "@/components/base/Label";
import { REASONING_TAGS } from "@/lib/constants/trading";
import { VALIDATION_LIMITS } from "@/lib/constants/validation";
import {
  useCustomTags,
  useCreateCustomTag,
  useDeleteCustomTag,
} from "@/hooks/useCustomTags";
import { cn } from "@/lib/utils";
import type { ReasoningTag } from "@/types/database";

const { CUSTOM_TAG_MAX_LEN, CUSTOM_TAG_MAX_COUNT } = VALIDATION_LIMITS;

// ToggleChipGrid 와 동일한 칩 시각 — 프리셋/커스텀 칩이 한 그리드에서 구분 없이 보이게 한다.
const CHIP_BASE =
  "rounded-xl border px-3 py-2.5 text-[13px] font-semibold transition-colors";
const CHIP_SELECTED = "bg-primary text-primary-foreground border-primary";
const CHIP_UNSELECTED = "border-border bg-muted/50 text-muted-foreground";

interface AnalysisTagsFieldProps {
  reasoningTags: ReasoningTag[];
  customTags: string[];
  onReasoningChange: (next: ReasoningTag[]) => void;
  onCustomChange: (next: string[]) => void;
}

export function AnalysisTagsField({
  reasoningTags,
  customTags,
  onReasoningChange,
  onCustomChange,
}: AnalysisTagsFieldProps) {
  const registry = useCustomTags();
  const [sheetOpen, setSheetOpen] = useState(false);

  function toggleReasoning(tag: ReasoningTag) {
    onReasoningChange(
      reasoningTags.includes(tag)
        ? reasoningTags.filter((t) => t !== tag)
        : [...reasoningTags, tag],
    );
  }

  function toggleCustom(label: string) {
    if (customTags.includes(label)) {
      onCustomChange(customTags.filter((t) => t !== label));
      return;
    }
    // 선택 개수 제한은 추가 시점에만 enforce(프리셋과 무관).
    if (customTags.length >= CUSTOM_TAG_MAX_COUNT) return;
    onCustomChange([...customTags, label]);
  }

  // 레지스트리 라벨 ∪ 현재 선택된 라벨(레지스트리에서 삭제된 과거 라벨도 선택분이면 노출).
  const registryLabels = registry.map((t) => t.label);
  const customLabels = [
    ...registryLabels,
    ...customTags.filter((l) => !registryLabels.includes(l)),
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {REASONING_TAGS.map((opt) => {
        const selected = reasoningTags.includes(opt.value);
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => toggleReasoning(opt.value)}
            className={cn(CHIP_BASE, selected ? CHIP_SELECTED : CHIP_UNSELECTED)}
          >
            {opt.label}
          </button>
        );
      })}

      {customLabels.map((label) => {
        const selected = customTags.includes(label);
        return (
          <button
            key={label}
            type="button"
            onClick={() => toggleCustom(label)}
            className={cn(
              CHIP_BASE,
              "max-w-full break-all text-left",
              selected ? CHIP_SELECTED : CHIP_UNSELECTED,
            )}
          >
            {label}
          </button>
        );
      })}

      <button
        type="button"
        aria-label="태그 추가"
        onClick={(e) => {
          // 시트가 열리며 조상에 aria-hidden 이 씌워지기 전에 트리거 포커스를 해제(접근성 경고 방지).
          e.currentTarget.blur();
          setSheetOpen(true);
        }}
        className={cn(
          CHIP_BASE,
          "inline-flex items-center gap-1 border-dashed border-border bg-transparent text-muted-foreground",
        )}
      >
        <PlusIcon className="size-4" />
      </button>

      <NewTagSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        registry={registry}
        customTags={customTags}
        onCustomChange={onCustomChange}
      />
    </div>
  );
}

interface NewTagSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  registry: { id: string; label: string }[];
  customTags: string[];
  onCustomChange: (next: string[]) => void;
}

function NewTagSheet({
  open,
  onOpenChange,
  registry,
  customTags,
  onCustomChange,
}: NewTagSheetProps) {
  const [draft, setDraft] = useState("");
  const createTag = useCreateCustomTag();
  const deleteTag = useDeleteCustomTag();

  const atMax = customTags.length >= CUSTOM_TAG_MAX_COUNT;

  async function handleCreate() {
    const label = draft.trim();
    if (!label || label.length > CUSTOM_TAG_MAX_LEN || createTag.isPending) return;
    try {
      const tag = await createTag.mutateAsync(label);
      // 레지스트리에 추가 + 현재 편집 거래에 자동 선택(개수 제한 내에서, 중복 방지).
      if (!customTags.includes(tag.label) && customTags.length < CUSTOM_TAG_MAX_COUNT) {
        onCustomChange([...customTags, tag.label]);
      }
      // 시트는 유지 — 연속 추가 가능. 입력만 초기화.
      setDraft("");
    } catch {
      // mutation 에러는 아래 인라인 메시지로 노출.
    }
  }

  async function handleDelete(tag: { id: string; label: string }) {
    if (deleteTag.isPending) return;
    try {
      await deleteTag.mutateAsync(tag.id);
      // 삭제된 라벨이 현재 폼에 선택돼 있으면 함께 해제.
      if (customTags.includes(tag.label)) {
        onCustomChange(customTags.filter((l) => l !== tag.label));
      }
    } catch {
      // noop — 인라인 에러로 노출.
    }
  }

  const errorMessage = createTag.isError
    ? "태그를 추가하지 못했어요."
    : deleteTag.isError
      ? "태그를 삭제하지 못했어요."
      : null;

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent aria-describedby={undefined}>
        <DrawerHeader>
          <DrawerTitle>사용자 태그</DrawerTitle>
        </DrawerHeader>
        <div className="space-y-4 px-5 pb-8">
          <div className="space-y-2">
            <Label htmlFor="new-custom-tag">새 태그</Label>
            <div className="relative">
              <Input
                id="new-custom-tag"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  // 한글 IME 조합 확정 Enter 는 무시(부분 음절 추가 방지).
                  if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    void handleCreate();
                  }
                }}
                maxLength={CUSTOM_TAG_MAX_LEN}
                placeholder={atMax ? `태그는 최대 ${CUSTOM_TAG_MAX_COUNT}개까지` : "태그 입력 후 추가"}
                className="pr-[68px]"
              />
              <Button
                type="button"
                size="sm"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 h-9 px-3.5 text-[13px]"
                onClick={() => void handleCreate()}
                disabled={!draft.trim() || createTag.isPending}
              >
                추가
              </Button>
            </div>
            {atMax && (
              <p className="text-[12px] text-muted-foreground">
                거래당 사용자 태그는 최대 {CUSTOM_TAG_MAX_COUNT}개까지 선택할 수 있어요.
              </p>
            )}
          </div>

          {registry.length > 0 && (
            <div className="space-y-2">
              <Label>등록된 태그</Label>
              <div className="flex flex-wrap gap-1.5">
                {registry.map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/50 px-3 py-1 text-[13px] font-semibold text-muted-foreground"
                  >
                    <span className="break-all text-left">{tag.label}</span>
                    <button
                      type="button"
                      aria-label={`${tag.label} 삭제`}
                      onClick={() => void handleDelete(tag)}
                      disabled={deleteTag.isPending}
                      className="shrink-0"
                    >
                      <XIcon className="size-3.5" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {errorMessage && <p className="text-sm text-destructive">{errorMessage}</p>}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
