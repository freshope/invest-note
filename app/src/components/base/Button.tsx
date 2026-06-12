import * as React from "react";
import { Button as UIButton, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const Button = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof UIButton>
>(({ className, ...props }, ref) => (
  <UIButton
    ref={ref}
    className={cn("rounded-xl font-semibold active:scale-[0.98]", className)}
    {...props}
  />
));
Button.displayName = "Button";

export { Button, buttonVariants };
