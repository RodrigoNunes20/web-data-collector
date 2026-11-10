import csv
import json
import tempfile
import unittest
from pathlib import Path

import openpyxl
import requests

from collector.cli import BOOK_SUMMARY, main
from collector.exporters import export
from collector.http import Fetcher, FetchError


class FakeResponse:
    def __init__(self, status=200, content=b"", json_data=None, encoding="ISO-8859-1"):
        self.status_code = status
        self.content = content
        self._json = json_data
        self.encoding = encoding

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FetcherTests(unittest.TestCase):
    def test_utf8_decoding_even_when_requests_guesses_latin1(self):
        session = FakeSession([FakeResponse(content="£51.77".encode("utf-8"))])
        self.assertEqual(Fetcher(delay=0, session=session).get_text("http://x"), "£51.77")

    def test_http_errors_become_fetch_errors(self):
        session = FakeSession([FakeResponse(status=404)])
        with self.assertRaises(FetchError) as ctx:
            Fetcher(delay=0, session=session).get_json("http://x")
        self.assertIn("404", str(ctx.exception))

    def test_rate_limit_message_has_a_hint(self):
        session = FakeSession([FakeResponse(status=403)])
        with self.assertRaises(FetchError) as ctx:
            Fetcher(delay=0, session=session).get_json("http://x")
        self.assertIn("rate limited", str(ctx.exception))

    def test_network_errors_become_fetch_errors(self):
        session = FakeSession([requests.ConnectionError("boom")])
        with self.assertRaises(FetchError):
            Fetcher(delay=0, session=session).get_text("http://x")

    def test_invalid_json(self):
        session = FakeSession([FakeResponse(content=b"<html>")])
        with self.assertRaises(FetchError):
            Fetcher(delay=0, session=session).get_json("http://x")

    def test_delay_between_requests(self):
        session = FakeSession([FakeResponse(content=b"a"), FakeResponse(content=b"b")])
        slept = []
        fetcher = Fetcher(delay=2.0, session=session, clock=lambda: 100.0, sleep=slept.append)
        fetcher.get_text("http://x/1")
        self.assertEqual(slept, [])  # no wait before the first request
        fetcher.get_text("http://x/2")
        self.assertEqual(slept, [2.0])


class ExportTests(unittest.TestCase):
    ROWS = [
        {"title": "Book A", "price_gbp": 10.0, "rating": 5, "in_stock": True, "url": "u1", "image_url": "i1"},
        {"title": "Book B é", "price_gbp": 20.0, "rating": 4, "in_stock": False, "url": "u2", "image_url": "i2"},
    ]
    COLUMNS = ["title", "price_gbp", "rating", "in_stock", "url", "image_url"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_csv_and_json(self):
        export(self.ROWS, self.dir / "o.csv", self.COLUMNS)
        with open(self.dir / "o.csv", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[1]["title"], "Book B é")
        export(self.ROWS, self.dir / "o.json", self.COLUMNS)
        data = json.loads((self.dir / "o.json").read_text(encoding="utf-8"))
        self.assertEqual(data[0]["price_gbp"], 10.0)
        self.assertEqual(data[1]["title"], "Book B é")

    def test_xlsx_has_summary_formulas_and_data(self):
        export(self.ROWS, self.dir / "o.xlsx", self.COLUMNS, BOOK_SUMMARY, "Books")
        wb = openpyxl.load_workbook(self.dir / "o.xlsx")
        self.assertEqual(wb.sheetnames, ["Summary", "Data"])
        self.assertEqual(wb["Data"].max_row, 3)
        self.assertEqual(wb["Summary"]["B4"].value, "=COUNTA(Data!$A$2:$A$3)")
        self.assertEqual(wb["Summary"]["B5"].value, "=IFERROR(AVERAGE(Data!$B$2:$B$3),0)")

    def test_unsupported_extension_and_empty_rows(self):
        with self.assertRaises(ValueError):
            export(self.ROWS, self.dir / "o.txt", self.COLUMNS)
        with self.assertRaises(ValueError):
            export([], self.dir / "o.xlsx", self.COLUMNS)


class CliTests(unittest.TestCase):
    def test_github_command_end_to_end_with_fake_network(self):
        payload = [
            {"name": "alpha", "stargazers_count": 3, "fork": False, "html_url": "https://github.com/u/alpha", "updated_at": "2026-01-02T00:00:00Z"},
        ]
        session = FakeSession([FakeResponse(json_data=payload)])
        fetcher = Fetcher(delay=0, session=session)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "repos.csv"
            code = main(["github", "u", "-o", str(out), "-q"], fetcher=fetcher)
            self.assertEqual(code, 0)
            self.assertIn("alpha", out.read_text(encoding="utf-8-sig"))

    def test_cli_reports_fetch_errors_with_exit_code_1(self):
        fetcher = Fetcher(delay=0, session=FakeSession([FakeResponse(status=404)]))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["github", "nobody", "-o", str(Path(tmp) / "x.csv"), "-q"], fetcher=fetcher), 1)

    def test_bad_output_extension_exit_code_2(self):
        payload = [{"name": "a", "html_url": "u"}]
        fetcher = Fetcher(delay=0, session=FakeSession([FakeResponse(json_data=payload)]))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["github", "u", "-o", str(Path(tmp) / "x.txt"), "-q"], fetcher=fetcher), 2)


if __name__ == "__main__":
    unittest.main()
