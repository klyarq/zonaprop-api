import cloudscraper


class Browser:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )

    def get(self, url):
        return self.scraper.get(url)

    def get_text(self, url):
        return self.scraper.get(url).text
