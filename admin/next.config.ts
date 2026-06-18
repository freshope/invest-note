import path from "node:path";
import type { NextConfig } from "next";

const workspaceRoot = path.join(process.cwd(), "..");

const nextConfig: NextConfig = {
  // Node 서버(standalone)로 서빙 — 컨테이너에 self-contained server.js 만 담아 배포(nginx 불필요).
  // 접근 가드는 클라이언트 + API 403(미들웨어 불필요).
  output: "standalone",
  // monorepo: 트레이싱 루트를 워크스페이스 루트로 고정해야 standalone 이 의존성을 올바로 포함한다.
  outputFileTracingRoot: workspaceRoot,
  // worktree 와 메인 repo 에 lockfile 이 둘 다 있으면 Turbopack 이 워크스페이스 루트를
  // 잘못 추론해 청크 경로가 깨진다(ChunkLoadError). next dev 는 항상 admin 에서 실행되므로
  // cwd 의 부모(pnpm-workspace.yaml 위치)를 루트로 고정. (app/next.config 와 동일)
  turbopack: { root: workspaceRoot },
};

export default nextConfig;
