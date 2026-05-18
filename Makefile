-include .makerc

DEVTOOLS_DIR ?= $(HOME)/devtools

# ── project config ──────────────────────────────
FE_PORT         := 3000
BE_PORT         := 8000
BE_APP          := invest_note_api.main:create_app
BE_PYTHONPATH   := src
BE_UVICORN_OPTS := --factory --reload
ARCHIVE_PREFIX  := InvestNote
# ────────────────────────────────────────────────

ifeq ($(wildcard $(DEVTOOLS_DIR)/Makefile.common),)
  $(error devtools 를 찾을 수 없음: $(DEVTOOLS_DIR)/Makefile.common — git clone <repo> $(DEVTOOLS_DIR), 또는 .makerc 에 DEVTOOLS_DIR 설정)
endif

include $(DEVTOOLS_DIR)/Makefile.common
