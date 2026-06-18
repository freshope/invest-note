import * as React from "react";
import { Input as UIInput } from "@/components/ui/input";

const Input = React.forwardRef<
  HTMLInputElement,
  React.ComponentProps<typeof UIInput>
>((props, ref) => <UIInput ref={ref} {...props} />);
Input.displayName = "Input";

export { Input };
