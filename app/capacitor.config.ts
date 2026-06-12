import type { CapacitorConfig } from "@capacitor/cli";
import { KeyboardResize } from "@capacitor/keyboard";

// OTA 매니페스트 결정 엔드포인트(BE 라우터 `/live-update/manifest`).
// 이 URL 은 네이티브에 구워져 스토어 재출시로만 교체되므로, 빌드 환경에 무관하게
// 프로덕션 BE 리터럴로 하드코딩한다. env(NEXT_PUBLIC_API_BASE_URL)를 섞으면
// cap sync 시점 셸에 dev/staging 값이 떠 있을 때 비프로덕션 엔드포인트가
// 출시 빌드에 박힐 수 있다(복구 불가 footgun). OTA 는 항상 프로덕션 BE 를 향한다.
const API_BASE = "https://invest-note-api.pixelwave.app";

const config: CapacitorConfig = {
  appId: "app.pixelwave.investnote",
  appName: "투자노트",
  webDir: "out",
  plugins: {
    CapacitorUpdater: {
      updateUrl: `${API_BASE}/live-update/manifest`,
      autoUpdate: true,
    },
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
