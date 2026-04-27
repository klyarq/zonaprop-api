import os
import time

USE_PLAYWRIGHT = os.environ.get("USE_PLAYWRIGHT", "false").lower() == "true"


class Browser:
    def __init__(self):
        if USE_PLAYWRIGHT:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-dev-shm-usage", "--disable-gpu"],
            )
            self._context = self._browser.new_context(
                locale="es-AR",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            self._page = self._context.new_page()
        else:
            import cloudscraper
            self._scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "darwin", "mobile": False}
            )

    def get_text(self, url):
        if USE_PLAYWRIGHT:
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            return self._page.content()
        return self._scraper.get(url).text

    def get(self, url):
        return self.get_text(url)

    def close(self):
        if USE_PLAYWRIGHT:
            self._browser.close()
            self._pw.stop()
