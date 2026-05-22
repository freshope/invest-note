import { cn } from "@/lib/utils";
import {
  Tabs as UITabs,
  TabsList as UITabsList,
  TabsTrigger as UITabsTrigger,
  TabsContent as UITabsContent,
  tabsListVariants,
} from "@/components/ui/tabs";
import type { ComponentProps } from "react";

function Tabs({ className, ...props }: ComponentProps<typeof UITabs>) {
  return <UITabs className={cn(className)} {...props} />;
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof UITabsList>) {
  return (
    <UITabsList
      className={cn("w-full rounded-xl bg-muted/60 h-10 p-1", className)}
      {...props}
    />
  );
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof UITabsTrigger>) {
  return (
    <UITabsTrigger
      className={cn(
        "rounded-lg text-[13px] font-semibold data-[state=active]:shadow-none",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof UITabsContent>) {
  return <UITabsContent className={cn(className)} {...props} />;
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants };
