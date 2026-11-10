import unittest
from pathlib import Path

from collector.books import crawl, parse_listing, parse_price

FIXTURES = Path(__file__).parent / "fixtures"
START = "https://books.toscrape.com/index.html"
PAGE2 = "https://books.toscrape.com/catalogue/page-2.html"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParsePriceTests(unittest.TestCase):
    def test_price_variants(self):
        self.assertEqual(parse_price("£51.77"), 51.77)
        self.assertEqual(parse_price("Â£53.74"), 53.74)  # garbled symbol from a wrong charset guess
        self.assertEqual(parse_price("10"), 10.0)

    def test_no_price(self):
        self.assertIsNone(parse_price(""))
        self.assertIsNone(parse_price("free"))


class ParseListingTests(unittest.TestCase):
    def test_page_one(self):
        books, next_url = parse_listing(read("books_page1.html"), START)
        self.assertEqual(len(books), 3)
        first, second, third = books
        self.assertEqual(first.title, "A Light in the Attic")  # full title attribute, not the shortened text
        self.assertEqual(first.price_gbp, 51.77)
        self.assertEqual(first.rating, 3)
        self.assertTrue(first.in_stock)
        self.assertEqual(first.url, "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html")
        self.assertEqual(
            first.image_url,
            "https://books.toscrape.com/media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg",
        )
        self.assertEqual(second.price_gbp, 53.74)
        self.assertEqual(second.rating, 1)
        self.assertFalse(third.in_stock)
        self.assertEqual(third.rating, 4)
        self.assertEqual(next_url, PAGE2)

    def test_last_page_has_no_next_and_resolves_relative_urls(self):
        books, next_url = parse_listing(read("books_page2.html"), PAGE2)
        self.assertEqual(len(books), 2)
        self.assertIsNone(next_url)
        self.assertEqual(books[0].url, "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html")
        self.assertTrue(books[1].title.startswith("Full Moon over Noah's Ark: An Odyssey"))
        self.assertTrue(books[1].image_url.startswith("https://books.toscrape.com/media/cache/"))

    def test_unrelated_html_returns_nothing(self):
        books, next_url = parse_listing("<html><body><p>hello</p></body></html>", START)
        self.assertEqual(books, [])
        self.assertIsNone(next_url)


class CrawlTests(unittest.TestCase):
    def setUp(self):
        self.pages = {START: read("books_page1.html"), PAGE2: read("books_page2.html")}
        self.requested: list[str] = []

    def get_html(self, url: str) -> str:
        self.requested.append(url)
        return self.pages[url]

    def test_follows_next_links(self):
        books = crawl(self.get_html, start_url=START, max_pages=10)
        self.assertEqual(len(books), 5)
        self.assertEqual(self.requested, [START, PAGE2])

    def test_respects_max_pages(self):
        books = crawl(self.get_html, start_url=START, max_pages=1)
        self.assertEqual(len(books), 3)
        self.assertEqual(self.requested, [START])

    def test_stops_on_loops(self):
        looping = read("books_page1.html").replace("catalogue/page-2.html", "index.html")
        calls = []

        def get_html(url):
            calls.append(url)
            return looping

        books = crawl(get_html, start_url=START, max_pages=10)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(books), 3)

    def test_progress_callback(self):
        seen = []
        crawl(self.get_html, start_url=START, on_page=lambda n, url, count: seen.append((n, count)))
        self.assertEqual(seen, [(1, 3), (2, 2)])


if __name__ == "__main__":
    unittest.main()
