dev:
	PYTHONPATH=src poetry run uvicorn invest_note_api.main:create_app --factory --reload --port 8000

test:
	poetry run pytest -v

.PHONY: dev test
