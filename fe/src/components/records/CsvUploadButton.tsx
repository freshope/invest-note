"use client";

import { Button } from "@/components/base/Button";
import { UploadIcon } from "lucide-react";

interface Props {
  onClick?: () => void;
}

export function CsvUploadButton({ onClick }: Props) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onClick}
      className="gap-1.5"
    >
      <UploadIcon className="h-3.5 w-3.5" />
      거래내역서 업로드
    </Button>
  );
}
