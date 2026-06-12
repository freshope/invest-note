#!/usr/bin/env node
// OTA 발행 스크립트 (Capacitor self-hosted OTA v1)
//
// 흐름: pnpm -C fe build → @capgo/cli bundle zip --json → R2 zip PUT →
//       HEAD 재검증 → manifest JSON 원자적 flip(PUT).
//
// 사용법:
//   node scripts/publish-ota.mjs [--dry-run] [--required-native x.y.z]
//
// --dry-run        R2 PUT 을 스킵하고 build+zip+manifest 생성·검증까지만 수행.
//                  R2 자격증명이 없으면 자동으로 dry-run 으로 폴백한다.
// --required-native <semver>
//                  manifest 의 required_native_version 을 명시 지정.
//                  미지정 시 .env OTA_REQUIRED_NATIVE 를 사용(= 현재 스토어 라이브 바이너리의
//                  마케팅 버전). 둘 다 없으면 중단한다(레포 version 으로 폴백하지 않는다).
//
// R2 자격증명은 루트 gitignored .env(릴리즈 전용)에서 로드한다(결정 4).
// fe public env(NEXT_PUBLIC_*, .env.development.local)에는 절대 두지 않는다.

import { execFileSync } from "node:child_process";
import { readFileSync, mkdtempSync, existsSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const FE = join(ROOT, "fe");

// ── 인자 파싱 ───────────────────────────────────────────────
const args = process.argv.slice(2);
let dryRunFlag = args.includes("--dry-run");
let requiredNativeOverride = null;
{
  const i = args.indexOf("--required-native");
  if (i !== -1) requiredNativeOverride = args[i + 1];
}

// ── 로깅 헬퍼 ───────────────────────────────────────────────
const log = (...a) => console.log("[publish-ota]", ...a);
const warn = (...a) => console.warn("[publish-ota] ⚠ ", ...a);
const die = (msg) => {
  console.error("[publish-ota] ✗", msg);
  process.exit(1);
};

// ── 루트 .env 로드 (의존성 없이 최소 파서) ──────────────────
function loadDotEnv() {
  const p = join(ROOT, ".env");
  const env = {};
  if (!existsSync(p)) return env;
  for (const line of readFileSync(p, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq === -1) continue;
    const k = t.slice(0, eq).trim();
    let v = t.slice(eq + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    env[k] = v;
  }
  return env;
}

const dotenv = loadDotEnv();
const getEnv = (k) => process.env[k] ?? dotenv[k] ?? "";

const R2 = {
  accountId: getEnv("R2_ACCOUNT_ID"),
  accessKeyId: getEnv("R2_ACCESS_KEY_ID"),
  secretAccessKey: getEnv("R2_SECRET_ACCESS_KEY"),
  bucket: getEnv("R2_BUCKET"),
  publicBase: getEnv("R2_PUBLIC_BASE_URL"), // 예: https://ota.invest-note.app
  // manifest 객체 키. BE live_update_manifest_url 이 가리키는 경로와 정합해야 한다.
  manifestKey: getEnv("R2_MANIFEST_KEY") || "manifest/latest.json",
};

const haveCreds =
  R2.accountId && R2.accessKeyId && R2.secretAccessKey && R2.bucket && R2.publicBase;

// 자격증명이 없으면 자동 dry-run 폴백.
let dryRun = dryRunFlag;
if (!dryRun && !haveCreds) {
  warn("R2 자격증명이 불완전하여 자동으로 --dry-run 으로 폴백한다.");
  warn("필요한 키: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL");
  dryRun = true;
}

// ── 버전 출처: fe/package.json (마케팅 버전, semver) ─────────
const fePkg = JSON.parse(readFileSync(join(FE, "package.json"), "utf8"));
const version = fePkg.version;
if (!version) die("fe/package.json 에서 version 을 읽지 못했다.");
// required_native = OTA 번들이 요구하는 최소 네이티브 버전 = "현재 스토어 라이브 바이너리의
// 마케팅 버전"이다. 레포의 fe/package.json version 은 OTA web-only 릴리즈마다 앞서가 스토어
// 바이너리와 싱크되지 않으므로(예: 레포 1.2.0 vs 스토어 1.1.23) default 로 쓰면 게이트가 너무
// 높아져 라이브 기기가 번들을 못 받는다. 그래서 별도 단일 출처(.env OTA_REQUIRED_NATIVE)에서
// 읽고, 네이티브를 실제 제출·승인할 때만 그 값을 갱신한다. 미설정 시 조용한 오발행 대신 중단.
const requiredNative = requiredNativeOverride || getEnv("OTA_REQUIRED_NATIVE");
if (!requiredNative) {
  die(
    "required_native 미설정 — --required-native <semver> 인자 또는 .env OTA_REQUIRED_NATIVE 를 설정하라.\n" +
      "  값 = 현재 스토어에 라이브로 승인된 네이티브 바이너리의 마케팅 버전(레포 version 아님)."
  );
}

log(`version=${version} required_native_version=${requiredNative} dryRun=${dryRun}`);

// ── 1. 정적 export 빌드 (fe/out) ────────────────────────────
log("1) pnpm -C fe build (정적 export → fe/out)");
execFileSync("pnpm", ["-C", "fe", "build"], { cwd: ROOT, stdio: "inherit" });
const OUT = join(FE, "out");
if (!existsSync(join(OUT, "index.html"))) {
  die(`빌드 산출물 누락: ${join(OUT, "index.html")} 가 없다.`);
}

// ── 2. capgo CLI 로 호환 zip + checksum 생성 ────────────────
// ⚠ 표준 zip/sha256sum 금지 — 플러그인 무결성 검증은 capgo CLI checksum 과만 일치한다.
// checksum 은 --json 출력에서 파싱(직접 계산 금지). 호출은 fe 핀 버전을 결정적으로.
const CAPGO_BIN = join(FE, "node_modules", ".bin", "capgo");
if (!existsSync(CAPGO_BIN)) {
  die(`@capgo/cli 미설치: ${CAPGO_BIN} 없음. 'pnpm -C fe add -D @capgo/cli' 필요.`);
}
const workDir = mkdtempSync(join(tmpdir(), "ota-"));
const zipPath = join(workDir, `${version}.zip`);
const objectKey = `bundles/${version}.zip`; // 버전 포함 불변 키

log("2) capgo bundle zip --json (호환 zip + checksum)");
const capgoOut = execFileSync(
  CAPGO_BIN,
  [
    "bundle",
    "zip",
    fePkg.appId ?? "app.pixelwave.investnote",
    "--path",
    OUT,
    "--bundle",
    version,
    "--name",
    zipPath,
    "--json",
  ],
  { cwd: ROOT, encoding: "utf8" }
);

let capgoJson;
try {
  // --json 출력은 마지막 JSON 객체. 앞선 로그 라인 가능성 대비 첫 '{' 부터 파싱.
  const start = capgoOut.indexOf("{");
  capgoJson = JSON.parse(capgoOut.slice(start));
} catch (e) {
  die(`capgo --json 파싱 실패. raw 출력:\n${capgoOut}`);
}
log("   capgo --json:", JSON.stringify(capgoJson));

const checksum = capgoJson.checksum;
if (!checksum) die("capgo --json 출력에 checksum 키가 없다.");
if (!existsSync(zipPath)) die(`zip 산출물 누락: ${zipPath}`);

// zip 루트 구조 검증: index.html 이 루트(또는 단일 폴더 내)에 있어야 한다.
verifyZipStructure(zipPath);

// ── 3. manifest JSON 구성 (02 스키마: 정확히 4키) ───────────
const url = `${R2.publicBase.replace(/\/$/, "")}/${objectKey}`;
const manifest = {
  version,
  url,
  checksum,
  required_native_version: requiredNative,
};
const manifestKeys = Object.keys(manifest).sort();
const expectedKeys = ["checksum", "required_native_version", "url", "version"];
if (JSON.stringify(manifestKeys) !== JSON.stringify(expectedKeys)) {
  die(`manifest 키 불일치: ${JSON.stringify(manifestKeys)} != ${JSON.stringify(expectedKeys)}`);
}
log("3) manifest JSON:", JSON.stringify(manifest));

// ── 4. R2 업로드 + 원자적 flip ──────────────────────────────
if (dryRun) {
  log("4) [dry-run] R2 PUT 스킵.");
  log(`   (실행 시) zip PUT  → s3://${R2.bucket || "<bucket>"}/${objectKey}`);
  log(`   (실행 시) manifest PUT → s3://${R2.bucket || "<bucket>"}/${R2.manifestKey}`);
  log("✅ dry-run 검증 통과: build + zip + checksum 파싱 + manifest 4키 정합.");
  log(`   zip: ${zipPath}`);
  process.exit(0);
}

await publishToR2({ zipPath, objectKey, manifest });
log("✅ 발행 완료.");

// ════════════════════════════════════════════════════════════
// 헬퍼
// ════════════════════════════════════════════════════════════

function verifyZipStructure(zip) {
  // unzip -l 로 엔트리 목록을 읽어 루트 index.html(또는 단일 폴더 내) 존재 확인.
  const listing = execFileSync("unzip", ["-Z1", zip], { encoding: "utf8" });
  const entries = listing.split("\n").map((s) => s.trim()).filter(Boolean);
  const hasRootIndex = entries.includes("index.html");
  // 단일 폴더 래핑 케이스: 모든 엔트리가 동일 top-level 폴더이고 그 안에 index.html
  const tops = new Set(entries.map((e) => e.split("/")[0]));
  const singleFolderIndex =
    tops.size === 1 &&
    entries.some((e) => /^[^/]+\/index\.html$/.test(e));
  if (!hasRootIndex && !singleFolderIndex) {
    die(
      `zip 구조 검증 실패: 루트(또는 단일 폴더 내) index.html 없음. 엔트리:\n${entries.slice(0, 20).join("\n")}`
    );
  }
  log(`   zip 구조 OK (index.html ${hasRootIndex ? "루트" : "단일 폴더 내"}).`);
}

async function publishToR2({ zipPath, objectKey, manifest }) {
  const { S3Client, PutObjectCommand, HeadObjectCommand } = await import(
    "@aws-sdk/client-s3"
  );
  const client = new S3Client({
    region: "auto",
    endpoint: `https://${R2.accountId}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: R2.accessKeyId,
      secretAccessKey: R2.secretAccessKey,
    },
  });

  // ① zip PUT (버전 포함 불변 키)
  const zipBody = readFileSync(zipPath);
  log(`4) zip PUT → s3://${R2.bucket}/${objectKey} (${zipBody.length} bytes)`);
  await client.send(
    new PutObjectCommand({
      Bucket: R2.bucket,
      Key: objectKey,
      Body: zipBody,
      ContentType: "application/zip",
    })
  );

  // ② HEAD 재검증 (존재 + 크기)
  const head = await client.send(
    new HeadObjectCommand({ Bucket: R2.bucket, Key: objectKey })
  );
  if (Number(head.ContentLength) !== zipBody.length) {
    die(`R2 HEAD 크기 불일치: ${head.ContentLength} != ${zipBody.length}`);
  }
  log(`   HEAD OK (size=${head.ContentLength}).`);

  // ③ manifest JSON PUT — 원자적 flip. zip 검증 후에만 일어난다.
  log(`5) manifest flip → s3://${R2.bucket}/${R2.manifestKey}`);
  await client.send(
    new PutObjectCommand({
      Bucket: R2.bucket,
      Key: R2.manifestKey,
      Body: JSON.stringify(manifest),
      ContentType: "application/json",
      CacheControl: "no-cache",
    })
  );
}
