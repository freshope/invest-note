"use client";

import { cn } from "@/lib/utils";

interface ProgressTrackProps {
  pct: number;
  colorClass: string;
  className?: string;
}

export function ProgressTrack({ pct, colorClass, className }: ProgressTrackProps) {
  return (
    <div className={cn("h-1.5 rounded-full bg-muted overflow-hidden", className)}>
      <div className={cn("h-full rounded-full", colorClass)} style={{ width: `${pct}%` }} />
    </div>
  );
}
