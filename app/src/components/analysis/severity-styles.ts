import { AlertTriangle, Info, AlertCircle } from "lucide-react";

export const SEVERITY_STYLES = {
  info: {
    bg: "bg-blue-50",
    border: "border-blue-200",
    icon: Info,
    iconClass: "text-blue-500",
    metricClass: "text-blue-600",
  },
  warn: {
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertTriangle,
    iconClass: "text-amber-500",
    metricClass: "text-amber-700",
  },
  critical: {
    bg: "bg-red-50",
    border: "border-red-200",
    icon: AlertCircle,
    iconClass: "text-red-500",
    metricClass: "text-red-600",
  },
} as const;
