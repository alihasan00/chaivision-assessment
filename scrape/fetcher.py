import asyncio
import base64
import json
import re
from pathlib import Path
from typing import Optional

import httpx

from bot.schemas import Product
from config import get_logger, settings
from scrape.exporter import save_to_csv, save_to_jsonl
from scrape.parsers import extract_product_details, extract_search_results

logger = get_logger(__name__)


class AmazonScraper:
    def __init__(self, use_local_html: bool = False):
        if not settings.zyte_api_key:
            raise ValueError("ZYTE_API_KEY not found in environment variables")

        self.auth = base64.b64encode(f"{settings.zyte_api_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {self.auth}",
            "Content-Type": "application/json",
        }
        self.client: Optional[httpx.AsyncClient] = None
        self.use_local_html = use_local_html

    async def __aenter__(self):
        logger.info("Initializing Amazon scraper with Zyte...")
        self.client = httpx.AsyncClient(timeout=settings.zyte_timeout)
        logger.info("Zyte client initialized successfully")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info("Closing Zyte client and cleaning up...")
        if self.client:
            await self.client.aclose()
        logger.info("Scraper shutdown complete")

    def _get_filename_from_url(self, url: str) -> Optional[str]:
        if "/s?k=" in url:
            query = url.split("/s?k=")[1].split("&")[0]
            return f"{settings.html_snapshots_dir}/search_{query}.html"
        if "/dp/" in url:
            asin_match = re.search(settings.asin_pattern, url)
            if asin_match:
                return (
                    f"{settings.html_snapshots_dir}/product_{asin_match.group(1)}.html"
                )
        return None

    def _save_page_html(self, url: str, html: str) -> None:
        filename = self._get_filename_from_url(url)
        if not filename:
            logger.warning(f"Could not generate filename for URL: {url}")
            return

        try:
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            Path(filename).write_text(html, encoding="utf-8")
            logger.info(f"Saved HTML snapshot to: {filename}")
        except Exception as e:
            logger.error(f"Error saving HTML snapshot: {e}")

    def _load_local_html(self, url: str) -> Optional[str]:
        try:
            filename = self._get_filename_from_url(url)
            if not filename:
                logger.error(f"Unknown URL pattern or could not extract ID: {url}")
                return None

            filepath = Path(filename)
            if not filepath.exists():
                logger.error(f"Local HTML file not found: {filename}")
                return None

            html = filepath.read_text(encoding="utf-8")
            logger.info(f"Loaded HTML from local file: {filename}")
            return html
        except Exception as e:
            logger.error(f"Error loading local HTML: {e}")
            return None

    async def _fetch_page_html(
        self, url: str, retry_count: int = 0, max_retries: int = None
    ) -> Optional[str]:
        max_retries = max_retries or settings.zyte_max_retries

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
            "geolocation": settings.zyte_geolocation,
            "device": settings.zyte_device,
            "sessionContext": [
                {
                    "name": "amazon_session",
                    "value": f"session_{hash(url) % settings.zyte_session_hash_mod}",
                }
            ],
            "actions": [
                {
                    "action": "waitForTimeout",
                    "timeout": settings.zyte_wait_timeout,
                }
            ],
        }

        try:
            response = await self.client.post(
                settings.zyte_api_url,
                headers=self.headers,
                content=json.dumps(payload),
            )

            if response.status_code == 520:
                if retry_count < max_retries:
                    wait_time = (
                        settings.retry_backoff_base**retry_count
                        * settings.retry_backoff_multiplier
                    )
                    logger.warning(
                        f"Website ban detected (520). Retrying in {wait_time}s... "
                        f"(attempt {retry_count + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    return await self._fetch_page_html(
                        url, retry_count + 1, max_retries
                    )
                logger.error(
                    f"Max retries reached for {url[:50]}... "
                    f"Zyte API returned status 520: {response.text}"
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
            return html

        except Exception as e:
            logger.error(f"Error fetching page via Zyte: {e}")
            return None

    async def get_top_products(self, url: str, n: int = None) -> list[dict]:
        n = n or settings.default_product_limit
        html = await self._fetch_page_html(url)
        if not html:
            logger.error("Failed to load search results page")
            return []

        try:
            return extract_search_results(html, n=n)
        except Exception as e:
            logger.error(f"Error extracting search results: {e}")
            return []

    async def get_product_details(self, url: str) -> Optional[Product]:
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
    query: str, n: int = None, use_local_html: bool = False
) -> list[Product]:
    n = n or settings.default_product_limit
    url = f"{settings.amazon_base_url}{settings.amazon_search_path}{query}"
    mode = "local HTML files" if use_local_html else "live scraping"
    logger.info(
        f"Starting to scrape top {n} products from: {url[:50]}... (mode: {mode})"
    )

    async with AmazonScraper(use_local_html=use_local_html) as scraper:
        basic_products = await scraper.get_top_products(url, n=n)
        if use_local_html and basic_products:
            snap_dir = Path(settings.html_snapshots_dir)
            filtered = []
            for p in basic_products:
                url_str = p.get("url") or ""
                asin_match = re.search(settings.asin_pattern, url_str)
                if (
                    asin_match
                    and (snap_dir / f"product_{asin_match.group(1)}.html").exists()
                ):
                    filtered.append(p)
            skipped = len(basic_products) - len(filtered)
            basic_products = filtered
            if skipped:
                logger.info(
                    f"Local HTML mode: using {len(basic_products)} products with snapshots (skipping {skipped} without local files)"
                )
        logger.info(f"Found {len(basic_products)} products to process")

        tasks = []
        for idx, product in enumerate(basic_products, 1):
            tasks.append(
                asyncio.create_task(scraper.get_product_details(product["url"]))
            )
            if idx < len(basic_products):
                await asyncio.sleep(settings.product_delay_seconds)

        results = await asyncio.gather(*tasks)
        detailed_products = [p for p in results if p is not None]

    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

    products_dicts = [p.model_dump(exclude_none=True) for p in detailed_products]
    save_to_jsonl(products_dicts, filename=settings.products_jsonl)
    save_to_csv(products_dicts, filename=settings.products_csv)
    logger.info(
        f"✓ Scraping complete! Successfully extracted {len(detailed_products)}/{len(basic_products)} products"
    )
    return detailed_products
