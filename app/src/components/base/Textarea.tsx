import { cn } from "@/lib/utils";
import { Textarea as TextareaUI } from "@/components/ui/textarea";
import type { ComponentProps } from "react";

function Textarea({ className, ...props }: ComponentProps<typeof TextareaUI>) {
  return (
    <TextareaUI
      className={cn(
        "min-h-[80px] rounded-xl border-0 bg-muted px-4 py-3 text-[15px] resize-none",
        className
      )}
      {...props}
    />
  );
}

export { Textarea };
