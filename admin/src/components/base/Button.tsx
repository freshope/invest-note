import * as React from "react";
import { Button as UIButton, buttonVariants } from "@/components/ui/button";

const Button = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<typeof UIButton>
>((props, ref) => <UIButton ref={ref} {...props} />);
Button.displayName = "Button";

export { Button, buttonVariants };
