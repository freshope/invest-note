import { AlertTriangle, Info, AlertCircle } from "lucide-react";

export const SEVERITY_STYLES = {
  info: {
    bg: "bg-blue-50 dark:bg-blue-950/30",
    border: "border-blue-200 dark:border-blue-800",
    icon: Info,
    iconClass: "text-blue-500",
    metricClass: "text-blue-600 dark:text-blue-400",
  },
  warn: {
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-800",
    icon: AlertTriangle,
    iconClass: "text-amber-500",
    metricClass: "text-amber-600 dark:text-amber-400",
  },
  critical: {
    bg: "bg-red-50 dark:bg-red-950/30",
    border: "border-red-200 dark:border-red-800",
    icon: AlertCircle,
    iconClass: "text-red-500",
    metricClass: "text-red-600 dark:text-red-400",
  },
} as const;
