-include .makerc

DEVTOOLS_DIR ?= $(HOME)/devtools

# ── 프로젝트 구성 (이름 = 폴더명) ────────────────
PROJECTS := fe be

# fe — Next.js + Capacitor 모바일 앱
fe_FRAMEWORK      := nextjs
fe_PORT           := 3000
fe_MOBILE         := 1
fe_ARCHIVE_PREFIX := InvestNote
fe_OTA            := 1

# be — FastAPI
be_FRAMEWORK    := fastapi
be_PORT         := 8000
be_APP          := invest_note_api.main:create_app
be_PYTHONPATH   := src
be_UVICORN_OPTS := --factory --reload
# ────────────────────────────────────────────────

ifeq ($(wildcard $(DEVTOOLS_DIR)/Makefile.common),)
  $(error devtools 를 찾을 수 없음: $(DEVTOOLS_DIR)/Makefile.common — git clone <repo> $(DEVTOOLS_DIR), 또는 .makerc 에 DEVTOOLS_DIR 설정)
endif

include $(DEVTOOLS_DIR)/Makefile.common
