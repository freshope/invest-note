import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { FieldErrors } from "react-hook-form"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getFirstFormError(errors: FieldErrors): string | undefined {
  return errors.root?.message ?? (Object.values(errors)[0]?.message as string | undefined);
}
