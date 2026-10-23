from __future__ import annotations

import uvicorn

from .api import create_app
from .config import get_settings


settings = get_settings()
app = create_app(settings)


def run() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
