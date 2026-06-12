"""종목 마스터 적재 CLI 진입점 — thin shim.

본체는 invest_note_api.services.stock_seed 로 이동(웹 라우터와 공유).

사용법:
    cd api
    poetry run python scripts/seed_stocks.py
"""

import sys
from pathlib import Path

# pyproject.toml 이 package-mode=false 라 invest_note_api 가 site-packages 에 없다.
_API_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from invest_note_api.services.stock_seed import main  # noqa: E402

if __name__ == "__main__":
    main()
