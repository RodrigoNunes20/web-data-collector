# Web Data Collector

A small, polite command-line tool that **collects data from web pages and JSON APIs** and saves it as a clean **Excel, CSV or JSON** file. Excel exports include a Summary sheet whose figures are live formulas.

Built with Python, Requests, BeautifulSoup and openpyxl.

It ships with two ready-to-use collectors, and a structure that makes adding a third one quick:

| Command | Source | Type | Output columns |
|---|---|---|---|
| `books` | [books.toscrape.com](https://books.toscrape.com/) (a sandbox site built for practising web scraping) | HTML pages with pagination | title, price, rating, in stock, URL, image URL |
| `github` | GitHub public REST API | JSON API with pagination | name, description, language, stars, forks, open issues, last update, fork?, URL |

## Quick start

```bash
git clone https://github.com/<your-user>/web-data-collector.git
cd web-data-collector
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Scrape the first 3 listing pages (60 books) into Excel
python -m collector books --max-pages 3 -o books.xlsx

# List a GitHub user's public repositories, skipping forks
python -m collector github <username> --skip-forks -o repos.xlsx
```

The output format is chosen from the file extension: `.xlsx`, `.csv` or `.json`.

### Options

| Option | Applies to | Description |
|---|---|---|
| `-o, --output` | all | Output file, required |
| `--delay` | all | Seconds to wait between requests (default `1.0`) |
| `-q, --quiet` | all | Only print errors |
| `--max-pages` | books | Maximum number of listing pages, 20 books each (default `5`) |
| `--start-url` | books | First page to read (default: the site home page) |
| `--skip-forks` | github | Leave out forked repositories |

Optional: set the `GITHUB_TOKEN` environment variable to raise GitHub's anonymous rate limit (60 requests per hour).

Exit codes: `0` success, `1` network error or no data found, `2` invalid options.

## Example of the Excel output (books)

Summary sheet (formulas): total books, average / cheapest / most expensive price, how many are in stock, and a count per star rating.
Data sheet: one row per book, with header styling, filters and a frozen header row.

| title | price_gbp | rating | in_stock | url |
|---|---|---|---|---|
| A Light in the Attic | 51.77 | 3 | True | https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html |
| Tipping the Velvet | 53.74 | 1 | True | https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html |

## Why it is reliable

- **Polite by default**: identifies itself with a User-Agent, waits between requests, and never fetches pages in parallel.
- **Retries with backoff** on temporary server errors (429, 500, 502, 503, 504) and respects `Retry-After`.
- **Clear errors**: network failures, HTTP errors (with a rate-limit hint), invalid JSON and wrong output formats produce a readable message and a proper exit code, never a stack trace.
- **Charset safe**: pages are decoded as UTF-8 so symbols like `£` are not garbled, and the price parser also tolerates already-garbled text.
- **Loop safe**: pagination stops on repeated URLs and at `--max-pages`.
- **Failing early**: an unsupported output extension is rejected before any request is made.

## Tests

```bash
python -m unittest discover -s tests -v
```

27 tests, all running **offline** against saved HTML fixtures and fake HTTP sessions, so they are fast and never depend on the internet. They cover parsing, URL resolution, pagination, loops, retries and error handling, the GitHub paging logic, the exporters and the CLI.

## Project structure

```
collector/
  http.py        # polite HTTP client (timeouts, retries, delay, UTF-8 decoding)
  books.py       # HTML parser + pagination crawler
  github.py      # JSON API collector with pagination
  exporters.py   # CSV / JSON / Excel writers (Excel with formula summary)
  cli.py         # command line interface
tests/           # offline tests and HTML fixtures
```

## Adding a new collector

1. Create `collector/mysite.py` with a pure `parse_...(html, url)` function (easy to test with a saved page) and a function that follows pagination.
2. Define its `COLUMNS` and a summary list of `(label, formula, number format)` like `BOOK_SUMMARY` in `cli.py`.
3. Register a sub-command in `build_parser` and `main`.

## Responsible use

Only collect data you are allowed to collect. Before scraping any real website, read its terms of service and `robots.txt`, keep the delay reasonable, and prefer an official API when one exists. The `books` collector targets a site that exists specifically for scraping practice.

## License

MIT
