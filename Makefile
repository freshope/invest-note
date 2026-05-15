SHELL := /bin/zsh

FE_PORT := 3000
BE_PORT := 8000
DEV_DIR := .dev
DEV_LOG_DIR := $(DEV_DIR)/logs
DEV_PID_DIR := $(DEV_DIR)/pids
NODE_BIN_DIR := $(shell dirname "$$(command -v node 2>/dev/null)")

DEV_SERVICES := $(filter be fe,$(MAKECMDGOALS))
ifeq ($(strip $(DEV_SERVICES)),)
DEV_SERVICES := be fe
endif

.PHONY: dev be fe

dev:
	@mkdir -p $(DEV_LOG_DIR) $(DEV_PID_DIR)
	@for service in $(DEV_SERVICES); do \
		case "$$service" in \
			be) \
				pids=$$(lsof -ti tcp:$(BE_PORT) -sTCP:LISTEN 2>/dev/null || true); \
				if [ -n "$$pids" ]; then \
					kill $$pids 2>/dev/null || true; \
					for _ in {1..50}; do \
						remaining=$$(lsof -ti tcp:$(BE_PORT) -sTCP:LISTEN 2>/dev/null || true); \
						[ -z "$$remaining" ] && break; \
						sleep 0.1; \
					done; \
					remaining=$$(lsof -ti tcp:$(BE_PORT) -sTCP:LISTEN 2>/dev/null || true); \
					if [ -n "$$remaining" ]; then kill -9 $$remaining 2>/dev/null || true; fi; \
				fi; \
				rm -f $(DEV_PID_DIR)/be.pid; \
				;; \
			fe) \
				pids=$$(lsof -ti tcp:$(FE_PORT) -sTCP:LISTEN 2>/dev/null || true); \
				if [ -n "$$pids" ]; then \
					kill $$pids 2>/dev/null || true; \
					for _ in {1..50}; do \
						remaining=$$(lsof -ti tcp:$(FE_PORT) -sTCP:LISTEN 2>/dev/null || true); \
						[ -z "$$remaining" ] && break; \
						sleep 0.1; \
					done; \
					remaining=$$(lsof -ti tcp:$(FE_PORT) -sTCP:LISTEN 2>/dev/null || true); \
					if [ -n "$$remaining" ]; then kill -9 $$remaining 2>/dev/null || true; fi; \
				fi; \
				rm -f $(DEV_PID_DIR)/fe.pid; \
				;; \
		esac; \
	done
	@if [ "$(DEV_SERVICES)" = "be fe" ]; then \
		nohup sh -c 'cd be && exec env PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port $(BE_PORT)' > $(DEV_LOG_DIR)/be.log 2>&1 & echo $$! > $(DEV_PID_DIR)/be.pid; \
		nohup env PATH="$(NODE_BIN_DIR):$$PATH" sh -c 'cd fe && exec pnpm dev --hostname 127.0.0.1 --port $(FE_PORT)' > $(DEV_LOG_DIR)/fe.log 2>&1 & echo $$! > $(DEV_PID_DIR)/fe.pid; \
		echo "Started be on http://127.0.0.1:$(BE_PORT) (log: $(DEV_LOG_DIR)/be.log)"; \
		echo "Started fe on http://127.0.0.1:$(FE_PORT) (log: $(DEV_LOG_DIR)/fe.log)"; \
	elif [ "$(DEV_SERVICES)" = "be" ]; then \
		nohup sh -c 'cd be && exec env PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port $(BE_PORT)' > $(DEV_LOG_DIR)/be.log 2>&1 & echo $$! > $(DEV_PID_DIR)/be.pid; \
		echo "Started be on http://127.0.0.1:$(BE_PORT) (log: $(DEV_LOG_DIR)/be.log)"; \
	elif [ "$(DEV_SERVICES)" = "fe" ]; then \
		nohup env PATH="$(NODE_BIN_DIR):$$PATH" sh -c 'cd fe && exec pnpm dev --hostname 127.0.0.1 --port $(FE_PORT)' > $(DEV_LOG_DIR)/fe.log 2>&1 & echo $$! > $(DEV_PID_DIR)/fe.pid; \
		echo "Started fe on http://127.0.0.1:$(FE_PORT) (log: $(DEV_LOG_DIR)/fe.log)"; \
	else \
		echo "Usage: make dev [be|fe]"; \
		exit 2; \
	fi

be fe:
	@:

# ── 모바일 앱 빌드 (pnpm build + cap sync) ─────────────────────────────
# Next.js 정적 빌드 후 Capacitor 로 네이티브 프로젝트(ios/android) 동기화.
BUILD_TARGETS := $(filter ios android,$(MAKECMDGOALS))
ifeq ($(strip $(BUILD_TARGETS)),)
BUILD_TARGETS := ios android
endif

.PHONY: build run archive ios android

build:
	@cd fe && pnpm build:mobile
	@if [ "$(BUILD_TARGETS)" = "ios android" ]; then \
		echo "→ npx cap sync (ios + android)"; \
		cd fe && npx cap sync; \
	else \
		echo "→ npx cap sync $(BUILD_TARGETS)"; \
		cd fe && npx cap sync $(BUILD_TARGETS); \
	fi

run:
	@if [ "$(filter ios,$(MAKECMDGOALS))" != "ios" ] || [ -n "$(filter-out run ios,$(MAKECMDGOALS))" ]; then \
		echo "Usage: make run ios"; \
		exit 2; \
	fi
	@cd fe && pnpm build:mobile
	@echo "→ npx cap sync ios"
	@cd fe && npx cap sync ios
	@echo "→ npx cap run ios"
	@cd fe && npx cap run ios

ios android:
	@:

# ── 모바일 앱 아카이브 (Xcode Organizer 오픈까지) ─────────────────────
# xcodebuild archive → Organizer 오픈만 수행. (build / cap sync / bump-build 미포함)
# 사전 준비는 별도로: make bump-build && make build ios
#   - 새 마케팅 릴리즈면 bump-build 대신 bump-{patch|minor|major}
# 업로드는 Organizer 의 Distribute App → App Store Connect 로 수동 진행.
archive:
	@if [ "$(filter ios,$(MAKECMDGOALS))" != "ios" ] || [ -n "$(filter-out archive ios,$(MAKECMDGOALS))" ]; then \
		echo "Usage: make archive ios"; \
		exit 2; \
	fi
	@ARCHIVE_DIR="$$HOME/Library/Developer/Xcode/Archives/$$(date +%Y-%m-%d)"; \
	  mkdir -p "$$ARCHIVE_DIR"; \
	  ARCHIVE_PATH="$$ARCHIVE_DIR/InvestNote-$$(date +%H-%M-%S).xcarchive"; \
	  echo "→ xcodebuild archive → $$ARCHIVE_PATH"; \
	  xcodebuild \
	    -project $(IOS_PROJ_DIR)/App.xcodeproj \
	    -scheme App \
	    -configuration Release \
	    -destination 'generic/platform=iOS' \
	    -archivePath "$$ARCHIVE_PATH" \
	    -allowProvisioningUpdates \
	    archive; \
	  echo "→ open $$ARCHIVE_PATH (Xcode Organizer)"; \
	  open "$$ARCHIVE_PATH"

# ── 버전 관리 ──────────────────────────────────────────────────────────
# Marketing version (SemVer X.Y.Z) 와 Build number (단조 증가 정수) 를 분리.
#   - 마케팅 버전: fe/package.json, be/pyproject.toml,
#                  iOS MARKETING_VERSION, Android versionName
#   - 빌드 번호  : iOS CURRENT_PROJECT_VERSION, Android versionCode
# 진실 소스: fe/package.json 의 version (마케팅), max(iOS,Android) build (빌드 번호).
# bump 명령은 네 파일을 한 번에 갱신 → 드리프트 발생 방지.
# 릴리즈 흐름:
#   1) make bump-{patch|minor|major}  (또는 TestFlight 재업로드는 bump-build)
#   2) CHANGELOG.md 항목 정리
#   3) git commit && git tag vX.Y.Z   (push 는 수동)
IOS_PROJ_DIR := fe/ios/App
IOS_PBXPROJ := $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj
ANDROID_GRADLE := fe/android/app/build.gradle
FE_PKG := fe/package.json
BE_PYPROJECT := be/pyproject.toml

.PHONY: version version-check version-sync bump-patch bump-minor bump-major bump-build _bump _apply

version:
	@PV=$$(node -p "require('./$(FE_PKG)').version"); \
	  BE=$$(grep -m1 '^version = ' $(BE_PYPROJECT) | sed -E 's/version = "([^"]+)"/\1/'); \
	  IMV=$$(grep -m1 "MARKETING_VERSION = " $(IOS_PBXPROJ) | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  IBV=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PBXPROJ) | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  ANN=$$(awk '/versionName/ {gsub(/"/,""); print $$2}' $(ANDROID_GRADLE)); \
	  ANC=$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE)); \
	  printf "Marketing version (SemVer)\n"; \
	  printf "  fe/package.json   : %s\n" "$$PV"; \
	  printf "  be/pyproject.toml : %s\n" "$$BE"; \
	  printf "  iOS marketing     : %s\n" "$$IMV"; \
	  printf "  Android name      : %s\n" "$$ANN"; \
	  printf "Build number (monotonic)\n"; \
	  printf "  iOS build         : %s\n" "$$IBV"; \
	  printf "  Android code      : %s\n" "$$ANC"

version-check:
	@PV=$$(node -p "require('./$(FE_PKG)').version"); \
	  BE=$$(grep -m1 '^version = ' $(BE_PYPROJECT) | sed -E 's/version = "([^"]+)"/\1/'); \
	  IMV=$$(grep -m1 "MARKETING_VERSION = " $(IOS_PBXPROJ) | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  IBV=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PBXPROJ) | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  ANN=$$(awk '/versionName/ {gsub(/"/,""); print $$2}' $(ANDROID_GRADLE)); \
	  ANC=$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE)); \
	  FAIL=0; \
	  if [ "$$PV" != "$$BE" ] || [ "$$PV" != "$$IMV" ] || [ "$$PV" != "$$ANN" ]; then \
	    echo "마케팅 버전 불일치: pkg=$$PV be=$$BE ios=$$IMV android=$$ANN"; FAIL=1; \
	  fi; \
	  if [ "$$IBV" != "$$ANC" ]; then \
	    echo "빌드 번호 불일치: ios=$$IBV android=$$ANC"; FAIL=1; \
	  fi; \
	  if [ "$$FAIL" = "0" ]; then echo "in sync: $$PV build $$IBV"; else exit 1; fi

# fe/package.json + max(iOS,Android) build 기준으로 BE/iOS/Android 강제 동기화
version-sync:
	@NEW_MV=$$(node -p "require('./$(FE_PKG)').version"); \
	  IBV=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PBXPROJ) | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  ANC=$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE)); \
	  NEW_BUILD=$$IBV; if [ "$$ANC" -gt "$$NEW_BUILD" ]; then NEW_BUILD=$$ANC; fi; \
	  $(MAKE) -s _apply NEW_MV="$$NEW_MV" NEW_BUILD="$$NEW_BUILD"

bump-patch:
	@$(MAKE) -s _bump TYPE=patch
bump-minor:
	@$(MAKE) -s _bump TYPE=minor
bump-major:
	@$(MAKE) -s _bump TYPE=major
bump-build:
	@$(MAKE) -s _bump TYPE=build

# 내부: TYPE 에 따라 새 마케팅/빌드 계산 후 _apply 호출
_bump:
	@CUR=$$(node -p "require('./$(FE_PKG)').version"); \
	  if ! printf "%s\n" "$$CUR" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
	    echo "fe/package.json 의 version 이 SemVer 가 아님: $$CUR"; exit 1; \
	  fi; \
	  IFS=. read -r MA MI PA <<< "$$CUR"; \
	  case "$(TYPE)" in \
	    major) NEW_MV="$$((MA+1)).0.0";; \
	    minor) NEW_MV="$$MA.$$((MI+1)).0";; \
	    patch) NEW_MV="$$MA.$$MI.$$((PA+1))";; \
	    build) NEW_MV="$$CUR";; \
	    *) echo "Usage: make bump-{patch|minor|major|build}"; exit 1;; \
	  esac; \
	  IBV=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PBXPROJ) | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  ANC=$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE)); \
	  CUR_BUILD=$$IBV; if [ "$$ANC" -gt "$$CUR_BUILD" ]; then CUR_BUILD=$$ANC; fi; \
	  NEW_BUILD=$$((CUR_BUILD + 1)); \
	  $(MAKE) -s _apply NEW_MV="$$NEW_MV" NEW_BUILD="$$NEW_BUILD"

# 내부: NEW_MV / NEW_BUILD 를 네 파일에 일괄 적용
_apply:
	@sed -i '' -E "s/MARKETING_VERSION = [^;]+;/MARKETING_VERSION = $(NEW_MV);/g" $(IOS_PBXPROJ)
	@sed -i '' -E "s/CURRENT_PROJECT_VERSION = [^;]+;/CURRENT_PROJECT_VERSION = $(NEW_BUILD);/g" $(IOS_PBXPROJ)
	@sed -i '' -E "s/versionName \"[^\"]+\"/versionName \"$(NEW_MV)\"/" $(ANDROID_GRADLE)
	@sed -i '' -E "s/versionCode [0-9]+/versionCode $(NEW_BUILD)/" $(ANDROID_GRADLE)
	@sed -i '' -E "s/^version = \"[^\"]+\"/version = \"$(NEW_MV)\"/" $(BE_PYPROJECT)
	@cd fe && npm version --no-git-tag-version --allow-same-version $(NEW_MV) >/dev/null
	@$(MAKE) -s version

help:
	@printf "사용법: make <target>\n\n"
	@printf "개발 서버\n"
	@printf "  dev                    be + fe 동시 시작 (기본 동작)\n"
	@printf "  dev be                 백엔드만 시작 (포트 $(BE_PORT))\n"
	@printf "  dev fe                 프론트엔드만 시작 (포트 $(FE_PORT))\n\n"
	@printf "모바일 앱 빌드\n"
	@printf "  build                  pnpm build + cap sync (ios + android)\n"
	@printf "  build ios              pnpm build + cap sync ios\n"
	@printf "  build android          pnpm build + cap sync android\n\n"
	@printf "모바일 앱 실행\n"
	@printf "  run ios                pnpm build + cap sync ios + cap run ios\n"
	@printf "                         (연결된 iPhone에 설치/실행)\n\n"
	@printf "모바일 앱 아카이브\n"
	@printf "  archive ios            xcodebuild archive → Xcode Organizer 오픈\n"
	@printf "                         (사전: make bump-build && make build ios)\n"
	@printf "                         (이후: Distribute App → App Store Connect 수동)\n\n"
	@printf "버전 관리\n"
	@printf "  version                네 파일의 현재 마케팅/빌드 버전 표시\n"
	@printf "  bump-patch             X.Y.Z → X.Y.(Z+1), build +1  (버그 수정)\n"
	@printf "  bump-minor             X.Y.Z → X.(Y+1).0, build +1  (기능 추가)\n"
	@printf "  bump-major             X.Y.Z → (X+1).0.0, build +1  (breaking)\n"
	@printf "  bump-build             마케팅 동일, build 만 +1     (TestFlight 재업로드)\n"
	@printf "  version-sync           fe/package.json 마케팅 + 최대 build 로 나머지 동기화\n"
	@printf "  version-check          마케팅/빌드 버전이 모든 파일에서 일치하는지 검증\n\n"
	@printf "기타\n"
	@printf "  help                   이 도움말 표시\n"
