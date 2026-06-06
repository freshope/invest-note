import type { CapacitorConfig } from "@capacitor/cli";
import { KeyboardResize } from "@capacitor/keyboard";

const config: CapacitorConfig = {
  appId: "app.pixelwave.investnote",
  appName: "투자노트",
  webDir: "out",
  plugins: {
    // capacitor-plugin-safe-area 가 edge-to-edge 인셋을 직접 다루므로
    // Capacitor 내장 SystemBars 의 인셋 처리는 비활성화한다 (충돌 방지).
    SystemBars: {
      insetsHandling: "disable",
    },
    SplashScreen: {
      launchShowDuration: 1000,
      launchAutoHide: true,
      launchFadeOutDuration: 300,
      backgroundColor: "#A78BFA",
      androidSplashResourceName: "splash",
      androidScaleType: "CENTER_CROP",
      showSpinner: false,
      // splashFullScreen/splashImmersive 금지: 활성화 시 스플래시 tearDown 이
      // setDecorFitsSystemWindows(true) 로 EdgeToEdge 를 해제해, 앱 재오픈 시
      // 네이티브 인셋 패딩 + CSS 변수가 중복 적용된다 (safe-area 2배 버그).
    },
    Keyboard: {
      resize: KeyboardResize.Native,
    },
  },
};

export default config;
