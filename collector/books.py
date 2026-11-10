"""Collector for https://books.toscrape.com/, a sandbox site made for practising web scraping."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

DEFAULT_START_URL = "https://books.toscrape.com/"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
COLUMNS = ["title", "price_gbp", "rating", "in_stock", "url", "image_url"]


@dataclass
class Book:
    title: str
    price_gbp: Optional[float]
    rating: Optional[int]
    in_stock: bool
    url: str
    image_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_price(text: str) -> Optional[float]:
    """'£51.77' (or a garbled 'Â£51.77') -> 51.77."""
    match = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(match.group()) if match else None


def parse_listing(html: str, page_url: str) -> tuple[list[Book], Optional[str]]:
    """Parse one listing page. Returns (books, absolute URL of the next page or None)."""
    soup = BeautifulSoup(html, "html.parser")
    books: list[Book] = []
    for pod in soup.select("article.product_pod"):
        link = pod.select_one("h3 a")
        if link is None:
            continue
        title = (link.get("title") or link.get_text()).strip()
        rating_tag = pod.select_one("p.star-rating")
        rating = None
        if rating_tag is not None:
            rating = next((RATINGS[c] for c in rating_tag.get("class", []) if c in RATINGS), None)
        price_tag = pod.select_one("p.price_color")
        availability = pod.select_one("p.availability")
        image = pod.select_one("img")
        books.append(
            Book(
                title=title,
                price_gbp=parse_price(price_tag.get_text()) if price_tag else None,
                rating=rating,
                in_stock="in stock" in (availability.get_text().lower() if availability else ""),
                url=urljoin(page_url, link.get("href", "")),
                image_url=urljoin(page_url, image.get("src", "")) if image else "",
            )
        )
    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link["href"]) if next_link and next_link.get("href") else None
    return books, next_url


def crawl(
    get_html: Callable[[str], str],
    start_url: str = DEFAULT_START_URL,
    max_pages: int = 5,
    on_page: Optional[Callable[[int, str, int], None]] = None,
) -> list[Book]:
    """Follow the 'next' links from `start_url`, up to `max_pages` pages."""
    books: list[Book] = []
    visited: set[str] = set()
    url: Optional[str] = start_url
    page = 0
    while url and page < max_pages and url not in visited:
        visited.add(url)
        page += 1
        page_books, next_url = parse_listing(get_html(url), url)
        books.extend(page_books)
        if on_page:
            on_page(page, url, len(page_books))
        url = next_url
    return books
