"use client";

import { useState } from "react";
import { Input } from "@/components/base/Input";
import { cn } from "@/lib/utils";
import { fmtNumberInput, formatNumberInput, parseNumberInput } from "@/lib/format";

interface NumericInputProps {
  value: number;
  onValueChange: (n: number) => void;
  id?: string;
  inputMode?: "numeric" | "decimal";
  placeholder?: string;
  inputRef?: React.Ref<HTMLInputElement>;
  readOnly?: boolean;
}

// 숫자 입력 — 타이핑 중 원시 문자열을 보존해 소수점 입력을 지원한다.
// 콤마 포맷은 유지하되, value(number)로 매 입력마다 되돌리면 "307." 의 소수점이 사라지므로
// 로컬 문자열 상태를 source 로 둔다. 외부에서 value 가 바뀌면(수수료 자동계산·전량 버튼) 동기화.
export function NumericInput({ value, onValueChange, id, inputMode = "numeric", placeholder = "0", inputRef, readOnly = false }: NumericInputProps) {
  const [text, setText] = useState(() => fmtNumberInput(value));
  const [prevValue, setPrevValue] = useState(value);
  // 외부 value 가 바뀌면(수수료 자동계산·전량 버튼) 동기화. render 중 파생 상태 갱신으로
  // effect 의 cascading render 를 피한다(react-hooks/set-state-in-effect).
  // 타이핑 중인 값과 숫자상 동일하면 덮어쓰지 않는다(소수점/후행 0 입력 보존).
  if (value !== prevValue) {
    setPrevValue(value);
    if (parseNumberInput(text) !== value) {
      setText(fmtNumberInput(value));
    }
  }
  return (
    <Input
      ref={inputRef}
      id={id}
      type="text"
      inputMode={inputMode}
      placeholder={placeholder}
      value={text}
      readOnly={readOnly}
      aria-readonly={readOnly || undefined}
      className={cn(readOnly && "text-muted-foreground cursor-not-allowed")}
      onChange={(e) => {
        if (readOnly) return;
        const formatted = formatNumberInput(e.target.value);
        setText(formatted);
        onValueChange(parseNumberInput(formatted));
      }}
    />
  );
}
