"""
Etsy Scraper Flask App

This Flask app exposes the Etsy scraping functionality as a simple web API and
HTML frontend. It is designed so you can deploy it on Vercel (or any serverless
host that supports Python/Flask). Instead of running from CLI, you can send an
HTTP GET request with a keyword query parameter.

Notes / caveats
- Etsy heavily uses JavaScript and may block automated scraping. For production
  use the official Etsy API. This app is for educational/demo use.
- Vercel Python runtimes require an `api/` folder with an entrypoint. You can
  rename this file to `api/index.py` and add the appropriate configuration in
  `vercel.json`.
"""

import logging
import os
import re
import time
import urllib.parse
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def parse_price(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    s = str(text)
    s = s.replace("\u2009", "").replace("\xa0", " ")
    s = re.sub(r"[^0-9.,-]+", " ", s).strip()
    if not s:
        return None
    s = s.replace(" ", "")
    if s.count(",") and s.count("."):
        s = s.replace(",", "")
    elif s.count(",") and not s.count("."):
        s = s.replace(",", ".")
    m = re.search(r"\d+\.\d+|\d+", s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def scrape_etsy(keyword: str, max_pages: int = 1, pause: float = 1.0, timeout: int = 10) -> List[Dict[str, object]]:
    base_url = "https://www.etsy.com/search?q="
    query = urllib.parse.quote_plus(keyword)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    results: List[Dict[str, object]] = []

    for page in range(1, max_pages + 1):
        url = f"{base_url}{query}&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            logging.warning("Network error while fetching page %d: %s", page, exc)
            break
        if resp.status_code != 200:
            logging.warning("Non-200 status code for page %d: %s", page, resp.status_code)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = soup.find_all(attrs={"data-listing-id": True}) or soup.find_all("li", class_="wt-list-unstyled") or soup.select("a.listing-link")
        for listing in listings:
            title = None
            title_tag = listing.find("h3")
            if title_tag:
                title = title_tag.get_text(strip=True)
            if not title:
                link = listing.find("a", href=True)
                if link:
                    title = (link.get("title") or link.get("aria-label") or link.get_text(strip=True))
            if not title:
                title = listing.get_text(separator=" ", strip=True)[:200]

            price = None
            price_tag = listing.find("span", class_="currency-value")
            if price_tag:
                price = parse_price(price_tag.get_text())
            if price is None:
                price = parse_price(listing.get_text(separator=" ", strip=True))
            if price is None:
                continue
            results.append({"title": title, "price": price})
        time.sleep(pause)

    results.sort(key=lambda x: x["price"])
    return results


@app.route("/")
def index():
    return "<h1>Etsy Scraper API</h1><p>Use /search?keyword=your+query</p>"


@app.route("/search")
def search():
    keyword = request.args.get("keyword")
    if not keyword:
        return jsonify({"error": "Missing 'keyword' parameter"}), 400
    max_pages = int(request.args.get("pages", 1))
    results = scrape_etsy(keyword, max_pages=max_pages)
    return jsonify(results)


# For Vercel: the handler must be the WSGI app object
# Vercel expects something like: from index import app
# If you rename this file to api/index.py, Vercel will detect it.

if __name__ == "__main__":
    # Local dev server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
