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

.PHONY: build run ios android

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

# ── 모바일 앱 버전 관리 ────────────────────────────────────────────────
# iOS Build Number(CFBundleVersion) 와 Marketing Version,
# Android versionCode/versionName, package.json 을 한 곳에서 관리.
# TestFlight 는 동일 Build Number 재업로드 불가 → archive 직전 매번 bump-build.
IOS_PROJ_DIR := fe/ios/App
ANDROID_GRADLE := fe/android/app/build.gradle
FE_PKG := fe/package.json

.PHONY: version bump-build set-version ios-archive-prep help

version:
	@MV=$$(grep -m1 "MARKETING_VERSION = " $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  BV=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  printf "iOS marketing : %s\niOS build     : %s\n" "$$MV" "$$BV"
	@printf "Android name  : %s\nAndroid code  : %s\n" \
	  "$$(awk '/versionName/ {gsub(/"/,""); print $$2}' $(ANDROID_GRADLE))" \
	  "$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE))"
	@printf "package.json  : %s\n" \
	  "$$(node -p "require('./$(FE_PKG)').version")"

bump-build:
	@CUR=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  NEW=$$((CUR + 1)); \
	  sed -i '' -E "s/CURRENT_PROJECT_VERSION = [^;]+;/CURRENT_PROJECT_VERSION = $$NEW;/g" $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj; \
	  printf "iOS CFBundleVersion : %s → %s\n" "$$CUR" "$$NEW"
	@CUR=$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE)); \
	  NEW=$$((CUR + 1)); \
	  sed -i '' "s/versionCode $$CUR/versionCode $$NEW/" $(ANDROID_GRADLE); \
	  printf "Android versionCode : %s → %s\n" "$$CUR" "$$NEW"
	@$(MAKE) -s version

set-version:
	@if ! printf "%s\n" "$(V)" | grep -Eq '^[0-9]+[.][0-9]+$$'; then echo "Usage: make set-version V=1.0"; exit 1; fi
	@sed -i '' -E "s/MARKETING_VERSION = [^;]+;/MARKETING_VERSION = $(V);/g" $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj
	@IOS_CUR=$$(grep -m1 "CURRENT_PROJECT_VERSION = " $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj | sed -E 's/.*= //; s/;//; s/[[:space:]]+//g'); \
	  ANDROID_CUR=$$(awk '/versionCode/ {print $$2}' $(ANDROID_GRADLE)); \
	  CUR=$$IOS_CUR; \
	  if [ "$$ANDROID_CUR" -gt "$$CUR" ]; then CUR=$$ANDROID_CUR; fi; \
	  NEW=$$((CUR + 1)); \
	  PKG_VERSION="$(V).$$NEW"; \
	  sed -i '' -E "s/CURRENT_PROJECT_VERSION = [^;]+;/CURRENT_PROJECT_VERSION = $$NEW;/g" $(IOS_PROJ_DIR)/App.xcodeproj/project.pbxproj; \
	  sed -i '' "s/versionCode [0-9][0-9]*/versionCode $$NEW/" $(ANDROID_GRADLE); \
	  cd fe && npm version --no-git-tag-version --allow-same-version $$PKG_VERSION >/dev/null
	@sed -i '' "s/versionName \".*\"/versionName \"$(V)\"/" $(ANDROID_GRADLE)
	@$(MAKE) -s version

ios-archive-prep: bump-build
	@cd fe && pnpm build:mobile && npx cap sync ios
	@echo "✅ Ready. Open Xcode → Product → Archive"

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
	@printf "모바일 앱 버전 관리\n"
	@printf "  version                iOS / Android / package.json 의 현재 버전 표시\n"
	@printf "  bump-build             iOS Build Number, Android versionCode 를 +1\n"
	@printf "                         (TestFlight 업로드 직전 매번 실행)\n"
	@printf "  set-version V=X.Y      마케팅 버전을 X.Y 로 셋팅 + Build Number 도 +1\n"
	@printf "                         package.json 은 X.Y.<Build Number> 로 설정\n"
	@printf "  ios-archive-prep       bump-build → pnpm build → cap sync ios\n"
	@printf "                         (Xcode Archive 직전 일괄 준비)\n\n"
	@printf "기타\n"
	@printf "  help                   이 도움말 표시\n"
