import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const versionPath = resolve(rootDir, "version.json");

const targets = [
  {
    path: "app/package.json",
    update(content, state) {
      const json = JSON.parse(content);
      json.version = state.version;
      return `${JSON.stringify(json, null, 2)}\n`;
    },
  },
  {
    path: "api/pyproject.toml",
    update(content, state) {
      return replaceOne(
        content,
        /^version = ".*"$/m,
        `version = "${state.version}"`,
      );
    },
  },
  {
    path: "app/android/app/build.gradle",
    update(content, state) {
      return replaceOne(
        replaceOne(content, /^\s*versionCode \d+$/m, `        versionCode ${state.build}`),
        /^\s*versionName ".*"$/m,
        `        versionName "${state.version}"`,
      );
    },
  },
  {
    path: "app/ios/App/App.xcodeproj/project.pbxproj",
    update(content, state) {
      return replaceMany(
        replaceMany(
          content,
          /CURRENT_PROJECT_VERSION = [^;]+;/g,
          `CURRENT_PROJECT_VERSION = ${state.build};`,
        ),
        /MARKETING_VERSION = [^;]+;/g,
        `MARKETING_VERSION = ${state.version};`,
      );
    },
  },
];

function readVersionState() {
  const state = JSON.parse(readFileSync(versionPath, "utf8"));
  validateState(state);
  return state;
}

function writeVersionState(state) {
  validateState(state);
  writeFileSync(versionPath, `${JSON.stringify(state, null, 2)}\n`);
}

function validateState(state) {
  if (!state || typeof state !== "object") {
    fail("version.json must contain an object.");
  }
  if (!isSemver(state.version)) {
    fail(`Invalid version "${state.version}". Use SemVer like 1.2.3.`);
  }
  if (!Number.isInteger(state.build) || state.build < 1) {
    fail(`Invalid build "${state.build}". Use a positive integer.`);
  }
}

function isSemver(version) {
  return /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(version);
}

function replaceOne(content, pattern, replacement) {
  if (!content.match(pattern)) {
    fail(`Pattern not found: ${pattern}`);
  }
  return content.replace(pattern, replacement);
}

function replaceMany(content, pattern, replacement) {
  if (!content.match(pattern)) {
    fail(`Pattern not found: ${pattern}`);
  }
  return content.replace(pattern, replacement);
}

function readTarget(target) {
  return readFileSync(resolve(rootDir, target.path), "utf8");
}

function sync() {
  const state = readVersionState();
  for (const target of targets) {
    const targetPath = resolve(rootDir, target.path);
    const current = readFileSync(targetPath, "utf8");
    const next = target.update(current, state);
    if (next !== current) {
      writeFileSync(targetPath, next);
      console.log(`updated ${target.path}`);
    }
  }
  console.log(`version ${state.version} build ${state.build}`);
}

function check() {
  const state = readVersionState();
  const mismatches = [];
  for (const target of targets) {
    const current = readTarget(target);
    const expected = target.update(current, state);
    if (expected !== current) {
      mismatches.push(target.path);
    }
  }

  if (mismatches.length > 0) {
    console.error("Version files are out of sync:");
    for (const path of mismatches) {
      console.error(`- ${path}`);
    }
    process.exit(1);
  }

  console.log(`version files are in sync: ${state.version} build ${state.build}`);
}

function setVersion(args) {
  const [version, buildArg] = args;
  if (!version) {
    fail("Usage: pnpm version:set <version> [build]");
  }

  const current = readVersionState();
  const build = buildArg === undefined ? current.build : Number(buildArg);
  writeVersionState({ version, build });
  sync();
}

function bump(args) {
  const [part] = args;
  if (!["major", "minor", "patch"].includes(part)) {
    fail("Usage: pnpm version:bump <major|minor|patch>");
  }

  const current = readVersionState();
  const [major, minor, patch] = current.version.split(/[+-]/)[0].split(".").map(Number);
  const nextVersion = {
    major: `${major + 1}.0.0`,
    minor: `${major}.${minor + 1}.0`,
    patch: `${major}.${minor}.${patch + 1}`,
  }[part];

  writeVersionState({
    version: nextVersion,
    build: current.build + 1,
  });
  sync();
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

const [command, ...args] = process.argv.slice(2);

switch (command) {
  case "sync":
    sync();
    break;
  case "check":
    check();
    break;
  case "set":
    setVersion(args);
    break;
  case "bump":
    bump(args);
    break;
  default:
    fail("Usage: node scripts/version.mjs <sync|check|set|bump>");
}
