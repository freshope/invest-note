"use client";

import { useEffect, useState } from "react";
import CountUp from "react-countup";
import { fmt } from "@/lib/format";

const formatValue = (n: number) => fmt(Math.round(n));

/**
 * 헤더 숫자 전용 count-up 래퍼.
 * - 최초 마운트: 0 → value
 * - value 변경(계좌 필터 전환): preserveValue 로 직전 값 → 새 value
 * - prefers-reduced-motion: 애니메이션 없이 즉시 표시
 */
export function CountUpNumber({ value }: { value: number }) {
  const reducedMotion = usePrefersReducedMotion();

  if (reducedMotion) return <>{formatValue(value)}</>;

  return (
    <CountUp end={value} duration={0.6} preserveValue formattingFn={formatValue} />
  );
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
