#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"

prompt_secret() {
  label="$1"
  if ! { : > /dev/tty; } 2> /dev/null; then
    printf "%s is required. Run from an interactive terminal or set the matching environment variable.\n" "$label" >&2
    exit 1
  fi
  printf "%s: " "$label" > /dev/tty
  stty -echo < /dev/tty
  IFS= read -r secret < /dev/tty
  stty echo < /dev/tty
  printf "\n" > /dev/tty
  printf "%s" "$secret"
}

export KEYSTORE_PATH="${KEYSTORE_PATH:-$HOME/keystores/invest-note-release.jks}"
export KEY_ALIAS="${KEY_ALIAS:-invest-note}"

if [ ! -f "$KEYSTORE_PATH" ]; then
  printf "Release keystore not found at %s\n" "$KEYSTORE_PATH" >&2
  exit 1
fi

if [ -z "${KEYSTORE_PASSWORD:-}" ]; then
  KEYSTORE_PASSWORD="$(prompt_secret "Keystore password")"
  export KEYSTORE_PASSWORD
fi

if [ -z "${KEY_PASSWORD:-}" ]; then
  KEY_PASSWORD="$(prompt_secret "Key password")"
  export KEY_PASSWORD
fi

pnpm -C "$ROOT_DIR/app" build:mobile
pnpm -C "$ROOT_DIR/app" cap sync android
cd "$ROOT_DIR/app/android"
./gradlew bundleRelease

mkdir -p app/release
cp app/build/outputs/bundle/release/app-release.aab app/release/app-release.aab
printf "Android App Bundle saved to %s\n" "$ROOT_DIR/app/android/app/release/app-release.aab"
