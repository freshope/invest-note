"use client";

import { toast } from "sonner";
import { Button } from "@/components/base/Button";
import { UploadIcon } from "lucide-react";

export function CsvUploadButton() {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => toast.info("파일 업로드는 준비중이에요", { id: "file-upload-wip" })}
      className="gap-1.5"
    >
      <UploadIcon className="h-3.5 w-3.5" />
      파일 업로드
    </Button>
  );
}
