package app.pixelwave.investnote;

import android.os.Bundle;
import android.view.View;
import android.webkit.WebView;

import androidx.activity.EdgeToEdge;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

import java.util.Locale;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 모든 Android 버전에서 WebView 가 노치/상태바 밑까지 그려지도록 edge-to-edge 활성화.
        // (targetSdk 36 이어도 강제 적용은 Android 15+ 기기에 한정되므로 명시 호출이 필요하다.)
        EdgeToEdge.enable(this);
        setupSafeAreaInsets();
    }

    /**
     * 네이티브 WindowInsets 를 읽어 `--safe-area-inset-*` CSS 변수로 주입한다.
     *
     * Chromium < 140 WebView 는 edge-to-edge 환경에서 `env(safe-area-inset-*)` 를 0 으로
     * 보고하는 버그가 있다. FE 는 `var(--safe-area-inset-top, env(safe-area-inset-top))` 로
     * 쓰므로, 여기서 주입한 변수가 우선 적용돼 구형 webview 에서도 콘텐츠가 노치를 피한다.
     * WebView 를 padding 으로 밀지 않고(인셋 미소비) 변수만 주입하므로 배경은 노치 밑까지
     * full-bleed 로 유지되고 콘텐츠만 인셋만큼 내려간다.
     * (검증: Galaxy S20 / WebView 111 에서 top 28px 주입 확인.)
     */
    private void setupSafeAreaInsets() {
        final WebView webView = getBridge().getWebView();
        // webview 본체가 아닌 부모 컨테이너에 리스너를 달아 Capacitor 의 webview/키보드 인셋
        // 처리를 덮어쓰지 않는다. 인셋 변경(회전/키보드 등) 시 재주입 트리거로만 쓴다.
        final View host =
            webView.getParent() instanceof View ? (View) webView.getParent() : webView;
        ViewCompat.setOnApplyWindowInsetsListener(host, (view, windowInsets) -> {
            injectInsets(webView);
            // 인셋을 소비하지 않고 그대로 전달 — full-bleed 유지.
            return windowInsets;
        });
        ViewCompat.requestApplyInsets(host);

        // 콜드 런치 시 위 인셋 패스는 SPA 로드 전에 끝나, about:blank 의 documentElement 에
        // 주입한 변수가 앱 페이지 로드 시 교체되며 사라진다. 페이지 로드가 끝날 때마다
        // 다시 주입해 로드된 문서에 변수가 항상 존재하도록 보장한다.
        webView.setWebViewClient(new BridgeWebViewClient(getBridge()) {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                injectInsets(view);
            }
        });
    }

    /**
     * 루트 WindowInsets(상위 뷰에서 소비되기 전 원본)를 직접 조회해 주입한다.
     * 리스너 콜백에 전달되는 인셋은 중간 뷰에서 이미 소비돼 0 일 수 있어, `env()` 가 참조하는
     * 것과 동일한 소스인 getRootWindowInsets 로 조회한다. 인셋을 못 읽으면(null) 0 으로
     * 덮어쓰지 않고 그대로 둔다 — env() 폴백을 망가뜨리지 않기 위함.
     */
    private void injectInsets(WebView webView) {
        WindowInsetsCompat windowInsets = ViewCompat.getRootWindowInsets(webView);
        if (windowInsets == null) {
            return;
        }
        Insets insets = windowInsets.getInsets(
            WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
        float density = getResources().getDisplayMetrics().density;
        String js = String.format(
            Locale.US,
            "var s=document.documentElement.style;"
                + "s.setProperty('--safe-area-inset-top','%dpx');"
                + "s.setProperty('--safe-area-inset-right','%dpx');"
                + "s.setProperty('--safe-area-inset-bottom','%dpx');"
                + "s.setProperty('--safe-area-inset-left','%dpx');",
            Math.round(insets.top / density),
            Math.round(insets.right / density),
            Math.round(insets.bottom / density),
            Math.round(insets.left / density));
        webView.evaluateJavascript(js, null);
    }
}
