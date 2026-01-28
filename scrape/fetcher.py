import asyncio
import os
import base64
import json
import re
import httpx
from typing import Optional
from dotenv import load_dotenv
from scrape.logger import get_logger
from scrape.parsers import extract_search_results, extract_product_details
from scrape.exporter import save_to_jsonl, save_to_csv
from bot.schemas import Product

load_dotenv()

logger = get_logger(__name__)


class AmazonScraper:
    def __init__(self, use_local_html=False):
        self.api_key = os.getenv("ZYTE_API_KEY")
        if not self.api_key:
            raise ValueError("ZYTE_API_KEY not found in environment variables")

        self.auth = base64.b64encode(f"{self.api_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
        }

        self.client = None
        self.use_local_html = use_local_html

    async def __aenter__(self):
        logger.info("Initializing Amazon scraper with Zyte...")
        self.client = httpx.AsyncClient(timeout=180.0)
        logger.info("Zyte client initialized successfully")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info("Closing Zyte client and cleaning up...")
        if self.client:
            await self.client.aclose()
        logger.info("Scraper shutdown complete")

    def _get_filename_from_url(self, url):
        if "/s?k=" in url:
            query = url.split("/s?k=")[1].split("&")[0]
            return f"html_snapshots/search_{query}.html"
        elif "/dp/" in url:
            asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
            if asin_match:
                asin = asin_match.group(1)
                return f"html_snapshots/product_{asin}.html"
        return None

    def _save_page_html(self, url, html):
        filename = self._get_filename_from_url(url)
        if not filename:
            logger.warning(f"Could not generate filename for URL: {url}")
            return

        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"Saved HTML snapshot to: {filename}")
        except Exception as e:
            logger.error(f"Error saving HTML snapshot: {e}")

    def _load_local_html(self, url):
        try:
            filename = self._get_filename_from_url(url)
            if not filename:
                logger.error(f"Unknown URL pattern or could not extract ID: {url}")
                return None

            if not os.path.exists(filename):
                logger.error(f"Local HTML file not found: {filename}")
                return None

            with open(filename, "r", encoding="utf-8") as f:
                html = f.read()

            logger.info(f"Loaded HTML from local file: {filename}")
            return html

        except Exception as e:
            logger.error(f"Error loading local HTML: {e}")
            return None

    async def _fetch_page_html(self, url, retry_count=0, max_retries=3):
        if self.use_local_html:
            html = self._load_local_html(url)
            if html:
                return html
            logger.warning("Failed to load local HTML, falling back to Zyte API")

        logger.info(
            f"Fetching page via Zyte (attempt {retry_count + 1}/{max_retries + 1}): {url[:50]}..."
        )

        payload = {
            "url": url,
            "browserHtml": True,
            "javascript": True,
            "geolocation": "US",
            "device": "desktop",
            "sessionContext": [
                {"name": "amazon_session", "value": f"session_{hash(url) % 1000}"}
            ],
            "actions": [
                {
                    "action": "waitForTimeout",
                    "timeout": 5,
                }
            ],
        }

        try:
            response = await self.client.post(
                "https://api.zyte.com/v1/extract",
                headers=self.headers,
                content=json.dumps(payload),
            )

            if response.status_code == 520:
                if retry_count < max_retries:
                    wait_time = (2**retry_count) * 2
                    logger.warning(
                        f"Website ban detected (520). Retrying in {wait_time}s... (attempt {retry_count + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    return await self._fetch_page_html(
                        url, retry_count + 1, max_retries
                    )
                else:
                    logger.error(
                        f"Max retries reached for {url[:50]}... Zyte API returned status 520: {response.text}"
                    )
                    return None

            if response.status_code != 200:
                logger.error(
                    f"Zyte API returned status {response.status_code}: {response.text}"
                )
                return None

            data = response.json()
            html = data.get("browserHtml")

            if not html:
                logger.error("No HTML content returned from Zyte API")
                return None

            logger.info(f"Successfully fetched HTML for: {url[:50]}...")

            # if not use_local_html:
            #     self._save_page_html(url, html)

            return html

        except Exception as e:
            logger.error(f"Error fetching page via Zyte: {e}")
            return None

    async def get_top_products(self, url, n=10):
        """Get top N products from search results page"""
        html = await self._fetch_page_html(url)
        if not html:
            logger.error("Failed to load search results page")
            return []

        try:
            products = extract_search_results(html)
            return products[:n]
        except Exception as e:
            logger.error(f"Error extracting search results: {e}")
            return []

    async def get_product_details(self, url) -> Optional[Product]:
        html = await self._fetch_page_html(url)
        if not html:
            logger.error(f"Failed to load product page: {url[:50]}...")
            return None

        try:
            logger.info(f"Extracting product details from: {url[:50]}...")
            product = extract_product_details(html, url)
            logger.info(
                f"Successfully extracted details for: {product.title or 'Unknown product'}"
            )
            return product
        except Exception as e:
            logger.error(f"Error extracting product details: {e}")
            return None


async def scrape_products(
    query: str, n: int = 10, use_local_html: bool = False
) -> list[Product]:
    url = f"https://www.amazon.com/s?k={query}"
    mode = "local HTML files" if use_local_html else "live scraping"
    logger.info(
        f"Starting to scrape top {n} products from: {url[:50]}... (mode: {mode})"
    )

    async with AmazonScraper(use_local_html=use_local_html) as scraper:
        basic_products = await scraper.get_top_products(url, n=n)
        logger.info(f"Found {len(basic_products)} products to process")

        detailed_products: list[Product] = []
        total = len(basic_products)
        tasks = []

        for idx, product in enumerate(basic_products, 1):
            logger.info(f"Processing product {idx}/{total}...")
            tasks.append(
                asyncio.create_task(scraper.get_product_details(product["url"]))
            )
            if idx < total:
                await asyncio.sleep(2)

        results = await asyncio.gather(*tasks)
        # Filter out None results (failed extractions)
        detailed_products = [p for p in results if p is not None]

    os.makedirs("data", exist_ok=True)

    # Convert Product models to dicts for export
    products_dicts = [p.model_dump(exclude_none=True) for p in detailed_products]
    save_to_jsonl(products_dicts, filename="data/products.jsonl")
    save_to_csv(products_dicts, filename="data/products.csv")
    logger.info(
        f"✓ Scraping complete! Successfully extracted {len(detailed_products)}/{total} products"
    )
    return detailed_products
