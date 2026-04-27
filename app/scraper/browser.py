import os
import requests


SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")


class Browser:
    def __init__(self):
        self.session = requests.Session()

    def _fetch(self, url):
        if SCRAPER_API_KEY:
            api_url = "http://api.scraperapi.com"
            params = {"api_key": SCRAPER_API_KEY, "url": url, "country_code": "ar"}
            return self.session.get(api_url, params=params, timeout=60)
        return self.session.get(url, timeout=30)

    def get(self, url):
        return self._fetch(url)

    def get_text(self, url):
        return self._fetch(url).text
