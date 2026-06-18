import * as React from "react";
import { Label as UILabel } from "@/components/ui/label";

const Label = React.forwardRef<
  React.ComponentRef<typeof UILabel>,
  React.ComponentProps<typeof UILabel>
>((props, ref) => <UILabel ref={ref} {...props} />);
Label.displayName = "Label";

export { Label };
