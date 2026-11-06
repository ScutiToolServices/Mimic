"""Run with uv run python -m src.run."""
import sys

import uvicorn

from src.app import build_app
from src.config import load_settings


def main() -> None:
    settings = load_settings()
    if settings.exposed_without_token:
        sys.exit("Mimic refuses to start: MIMIC_HOST is not a loopback address and INTERNAL_API_TOKEN is empty.")
    uvicorn.run(build_app(settings), host=settings.host, port=settings.port, log_level="info", workers=1)


if __name__ == "__main__":
    main()
