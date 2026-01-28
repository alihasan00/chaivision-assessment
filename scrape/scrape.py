import argparse
import asyncio
from scrape.fetcher import scrape_products
from scrape.logger import get_logger

logger = get_logger(__name__)


async def main():
    logger.info("Starting Amazon scraper with Zyte...")
    parser = argparse.ArgumentParser(
        description="Scrape top 10 Amazon products for a given search query"
    )
    parser.add_argument(
        "--q",
        type=str,
        required=True,
        help="Search query (e.g., 'massage gun', 'wireless headphones')",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="Number of products to scrape (default: 10)",
    )
    parser.add_argument(
        "--use-local-html",
        action="store_true",
        help="Use local HTML files from html_snapshots/ folder instead of live scraping",
    )
    args = parser.parse_args()

    await scrape_products(args.q, n=args.n, use_local_html=args.use_local_html)
    logger.info("Scraping completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
