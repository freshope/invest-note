-include .makerc

DEVTOOLS_DIR ?= $(HOME)/devtools

# ── 프로젝트 구성 (이름 = 폴더명) ────────────────
PROJECTS := app api admin

# app — Next.js + Capacitor 모바일 앱
app_FRAMEWORK      := nextjs
app_PORT           := 3100
app_MOBILE         := 1
app_ARCHIVE_PREFIX := InvestNote
app_OTA            := 1

# api — FastAPI
api_FRAMEWORK    := fastapi
api_PORT         := 3108
api_APP          := invest_note_api.main:create_app
api_PYTHONPATH   := src
api_UVICORN_OPTS := --factory --reload

# admin — Next.js 어드민 패널 (web-only, static export)
admin_FRAMEWORK  := nextjs
admin_PORT       := 3101
# ────────────────────────────────────────────────

ifeq ($(wildcard $(DEVTOOLS_DIR)/Makefile.common),)
  $(error devtools 를 찾을 수 없음: $(DEVTOOLS_DIR)/Makefile.common — git clone <repo> $(DEVTOOLS_DIR), 또는 .makerc 에 DEVTOOLS_DIR 설정)
endif

include $(DEVTOOLS_DIR)/Makefile.common
