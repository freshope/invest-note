"use client";

import { useRef } from "react";
import { Button } from "@/components/base/Button";
import { UploadIcon } from "lucide-react";

export function CsvUploadButton() {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      alert("CSV/엑셀 업로드 기능은 곧 추가될 예정이에요 📥");
      e.target.value = "";
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={handleFileChange}
        className="hidden"
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => inputRef.current?.click()}
        className="gap-1.5"
      >
        <UploadIcon className="h-3.5 w-3.5" />
        CSV 업로드
      </Button>
    </>
  );
}
