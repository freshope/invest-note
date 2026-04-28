"use client";

import { useRef, useState } from "react";
import { UploadCloudIcon } from "lucide-react";
import { Button } from "@/components/base/Button";

interface Props {
  brokerName: string;
  onFileSelect: (file: File) => void;
  isLoading: boolean;
}

export function FileStep({ brokerName, onFileSelect, isLoading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const accept = brokerName === "토스증권" ? ".pdf" : ".xlsx,.xls";

  const handleFile = (file: File) => {
    setSelectedFile(file);
    onFileSelect(file);
  };

  return (
    <div className="flex flex-col gap-6">
      <div
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-10 transition-colors",
          dragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/30",
        ].join(" ")}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
      >
        <UploadCloudIcon className="h-10 w-10 text-muted-foreground" />
        <div className="text-center">
          <p className="text-sm font-medium">
            {brokerName} 거래내역서를 드래그하거나 클릭해서 선택하세요
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {accept.replace(/\./g, "").toUpperCase()} 형식 지원
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </div>

      {selectedFile && (
        <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-4 py-3 text-sm">
          <span className="font-medium text-foreground">{selectedFile.name}</span>
          <span className="text-muted-foreground">
            ({(selectedFile.size / 1024).toFixed(0)} KB)
          </span>
        </div>
      )}

      {isLoading && (
        <p className="text-center text-sm text-muted-foreground animate-pulse">
          파일을 분석 중입니다...
        </p>
      )}
    </div>
  );
}
