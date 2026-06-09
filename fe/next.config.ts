import path from "node:path";
import type { NextConfig } from "next";
import pkg from "./package.json" with { type: "json" };

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // 로컬 Supabase site_url 이 127.0.0.1:3000 이라 로그인 후 그 호스트로 리다이렉트되는데,
  // Next dev 는 기본 origin(localhost)과 달라 HMR 웹소켓을 cross-origin 으로 차단한다(dev 전용 허용).
  allowedDevOrigins: ["127.0.0.1"],
  // 워크스페이스 루트를 fe 의 부모(pnpm-workspace.yaml·hoist 된 node_modules 위치)로 고정.
  // worktree 와 메인 repo 에 lockfile 이 둘 다 있으면 Turbopack 이 루트를 잘못 추론해
  // 청크 경로가 깨진다(ChunkLoadError). next dev 는 항상 fe 에서 실행되므로 cwd 의 부모가 루트.
  turbopack: { root: path.join(process.cwd(), "..") },
  env: {
    NEXT_PUBLIC_APP_VERSION: pkg.version,
  },
};

export default nextConfig;
