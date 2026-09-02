from __future__ import annotations

import os
import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
