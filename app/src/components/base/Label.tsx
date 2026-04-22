import * as React from "react";
import { Label as UILabel } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const Label = React.forwardRef<
  HTMLLabelElement,
  React.ComponentProps<typeof UILabel>
>(({ className, ...props }, ref) => (
  <UILabel
    ref={ref}
    className={cn("text-[13px] font-semibold text-muted-foreground", className)}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
