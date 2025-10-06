# -*- coding: utf-8 -*-
import logging
from .bot import build_app
from .config import WEBHOOK_URL, PORT, WEBHOOK_PATH

LOGGER = logging.getLogger("RPG")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def main() -> None:
    app = build_app()

    if WEBHOOK_URL:
        LOGGER.info("RPG Bot: режим Webhook (Render)...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=WEBHOOK_PATH,
            webhook_url=f"{WEBHOOK_URL.rstrip('/')}/{WEBHOOK_PATH}",
            drop_pending_updates=True,
        )
    else:
        LOGGER.info("RPG Bot: режим Long Polling (локально)...")
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
