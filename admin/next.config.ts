import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 정적 export SPA. middleware 미사용(export 에서 미동작), 접근 가드는 클라이언트 + API 403.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // worktree 와 메인 repo 에 lockfile 이 둘 다 있으면 Turbopack 이 워크스페이스 루트를
  // 잘못 추론해 청크 경로가 깨진다(ChunkLoadError). next dev 는 항상 admin 에서 실행되므로
  // cwd 의 부모(pnpm-workspace.yaml 위치)를 루트로 고정. (app/next.config 와 동일)
  turbopack: { root: path.join(process.cwd(), "..") },
};

export default nextConfig;
