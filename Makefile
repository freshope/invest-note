SHELL := /bin/zsh

FE_PORT := 3000
BE_PORT := 8000
API_DIR := api
APP_DIR := app
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
		nohup sh -c 'cd $(API_DIR) && exec env PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port $(BE_PORT)' > $(DEV_LOG_DIR)/be.log 2>&1 & echo $$! > $(DEV_PID_DIR)/be.pid; \
		nohup env PATH="$(NODE_BIN_DIR):$$PATH" pnpm -C $(APP_DIR) dev --hostname 127.0.0.1 --port $(FE_PORT) > $(DEV_LOG_DIR)/fe.log 2>&1 & echo $$! > $(DEV_PID_DIR)/fe.pid; \
		echo "Started be on http://127.0.0.1:$(BE_PORT) (log: $(DEV_LOG_DIR)/be.log)"; \
		echo "Started fe on http://127.0.0.1:$(FE_PORT) (log: $(DEV_LOG_DIR)/fe.log)"; \
	elif [ "$(DEV_SERVICES)" = "be" ]; then \
		nohup sh -c 'cd $(API_DIR) && exec env PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port $(BE_PORT)' > $(DEV_LOG_DIR)/be.log 2>&1 & echo $$! > $(DEV_PID_DIR)/be.pid; \
		echo "Started be on http://127.0.0.1:$(BE_PORT) (log: $(DEV_LOG_DIR)/be.log)"; \
	elif [ "$(DEV_SERVICES)" = "fe" ]; then \
		nohup env PATH="$(NODE_BIN_DIR):$$PATH" pnpm -C $(APP_DIR) dev --hostname 127.0.0.1 --port $(FE_PORT) > $(DEV_LOG_DIR)/fe.log 2>&1 & echo $$! > $(DEV_PID_DIR)/fe.pid; \
		echo "Started fe on http://127.0.0.1:$(FE_PORT) (log: $(DEV_LOG_DIR)/fe.log)"; \
	else \
		echo "Usage: make dev [be|fe]"; \
		exit 2; \
	fi

be fe:
	@:
