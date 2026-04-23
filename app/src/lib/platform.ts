import { Capacitor } from "@capacitor/core";

export const isNativePlatform = (): boolean =>
  typeof window !== "undefined" && Capacitor.isNativePlatform();

export const getPlatform = (): "ios" | "android" | "web" => {
  if (typeof window === "undefined") return "web";
  return Capacitor.getPlatform() as "ios" | "android" | "web";
};
