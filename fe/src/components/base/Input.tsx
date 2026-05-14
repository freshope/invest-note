import * as React from "react";
import { Input as UIInput } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<
  HTMLInputElement,
  React.ComponentProps<typeof UIInput>
>(({ className, ...props }, ref) => (
  <UIInput
    ref={ref}
    className={cn(
      "h-12 rounded-xl border-0 bg-muted px-4 text-[15px] font-medium placeholder:font-normal focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";

export { Input };
