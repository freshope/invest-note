import { isNativePlatform } from "./platform";

type ImpactLevel = "light" | "medium" | "heavy";

async function nativeImpact(level: ImpactLevel): Promise<boolean> {
  try {
    const { Haptics, ImpactStyle } = await import("@capacitor/haptics");
    const style =
      level === "heavy"
        ? ImpactStyle.Heavy
        : level === "medium"
          ? ImpactStyle.Medium
          : ImpactStyle.Light;
    await Haptics.impact({ style });
    return true;
  } catch {
    return false;
  }
}

function webVibrate(level: ImpactLevel): void {
  if (typeof navigator === "undefined" || typeof navigator.vibrate !== "function") {
    return;
  }
  const duration = level === "heavy" ? 25 : level === "medium" ? 15 : 8;
  try {
    navigator.vibrate(duration);
  } catch {
    // 일부 브라우저는 사용자 제스처 없이 vibrate 호출 시 throw — 무시
  }
}

export async function hapticImpact(level: ImpactLevel = "light"): Promise<void> {
  if (isNativePlatform()) {
    const ok = await nativeImpact(level);
    if (ok) return;
  }
  webVibrate(level);
}
