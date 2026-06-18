// shadcn chart 래퍼. helper 를 그대로 re-export 하고, 페이지/컴포넌트는 이 래퍼만 사용한다.
// recharts primitive(LineChart, Line, XAxis 등)는 서드파티 lib 이라 래퍼 대상이 아니며 직접 import 한다.
export {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  ChartStyle,
} from "@/components/ui/chart";
export type { ChartConfig } from "@/components/ui/chart";
