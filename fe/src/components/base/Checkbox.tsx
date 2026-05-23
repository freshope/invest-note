import * as React from "react";
import { Checkbox as UICheckbox } from "@/components/ui/checkbox";

const Checkbox = React.forwardRef<
  React.ElementRef<typeof UICheckbox>,
  React.ComponentProps<typeof UICheckbox>
>((props, ref) => <UICheckbox ref={ref} {...props} />);
Checkbox.displayName = "Checkbox";

export { Checkbox };
