"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/base/Input";
import { fmtNumberInput, formatNumberInput, parseNumberInput } from "@/lib/format";

interface NumericInputProps {
  value: number;
  onValueChange: (n: number) => void;
  id?: string;
  inputMode?: "numeric" | "decimal";
  placeholder?: string;
  inputRef?: React.Ref<HTMLInputElement>;
}

// 숫자 입력 — 타이핑 중 원시 문자열을 보존해 소수점 입력을 지원한다.
// 콤마 포맷은 유지하되, value(number)로 매 입력마다 되돌리면 "307." 의 소수점이 사라지므로
// 로컬 문자열 상태를 source 로 둔다. 외부에서 value 가 바뀌면(수수료 자동계산·전량 버튼) 동기화.
export function NumericInput({ value, onValueChange, id, inputMode = "numeric", placeholder = "0", inputRef }: NumericInputProps) {
  const [text, setText] = useState(() => fmtNumberInput(value));
  useEffect(() => {
    // 타이핑 중인 값과 숫자상 동일하면 덮어쓰지 않는다(소수점/후행 0 입력 보존).
    setText((prev) => (parseNumberInput(prev) === value ? prev : fmtNumberInput(value)));
  }, [value]);
  return (
    <Input
      ref={inputRef}
      id={id}
      type="text"
      inputMode={inputMode}
      placeholder={placeholder}
      value={text}
      onChange={(e) => {
        const formatted = formatNumberInput(e.target.value);
        setText(formatted);
        onValueChange(parseNumberInput(formatted));
      }}
    />
  );
}
