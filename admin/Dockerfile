# syntax=docker/dockerfile:1.7
# admin = Next.js(App Router) standalone 서버. 빌드 후 .next/standalone(self-contained server.js)만 담는다.
# nginx 불필요 — Node 가 직접 서빙(pixelwave-web 와 동일 패턴). context 는 repo 루트(pnpm workspace lockfile).
# NEXT_PUBLIC_* 는 빌드 타임에 구워진다(클라이언트 env) → GHA repo Variables 를 build-args 로 주입.

FROM node:22-alpine AS builder
RUN corepack enable
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1

# 매니페스트만 먼저 복사해 deps 레이어 캐시. app 매니페스트는 워크스페이스 해석용(설치는 admin 만).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY admin/package.json ./admin/package.json
COPY app/package.json ./app/package.json
# admin 서브트리만 설치 → app(Capacitor) 의존성 회피.
RUN pnpm install --frozen-lockfile --filter invest-note-admin

ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY

# 소스 복사(.dockerignore 가 node_modules/.next/out 제외 → 설치된 admin/node_modules 보존).
COPY admin ./admin
RUN pnpm -C admin build

FROM node:22-alpine AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

# tracing root=repo 루트 → standalone 내부 경로가 admin/server.js 로 보존된다.
COPY --from=builder --chown=nextjs:nodejs /repo/admin/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/admin/.next/static ./admin/.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "admin/server.js"]
