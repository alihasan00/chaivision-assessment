import json
import pandas as pd
from scrape.logger import get_logger

logger = get_logger(__name__)


def save_to_jsonl(products, filename="data/products.jsonl"):
    logger.info(f"Saving {len(products)} products to {filename}")
    try:
        df = pd.DataFrame(products)
        df.to_json(
            filename, orient="records", lines=True, force_ascii=False, index=False
        )
        logger.info(f"Successfully saved JSONL to {filename}")
    except Exception as e:
        logger.error(f"Failed to save JSONL: {e}")


def save_to_csv(products, filename="data/products.csv"):
    logger.info(f"Saving products CSV to {filename}")
    try:
        df = pd.DataFrame(products)

        # Convert list fields to JSON strings for CSV compatibility
        # We process a copy or apply to the dataframe directly
        list_cols = ["bullet_features", "breadcrumbs"]
        for col in list_cols:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: json.dumps(x) if isinstance(x, list) else x
                )

        column_order = [
            "asin",
            "title",
            "price",
            "rating",
            "review_count",
            "brand",
            "bullet_features",
            "breadcrumbs",
            "dimensions",
            "weight",
            "url",
            "image_url",
        ]

        # Ensure only existing columns are selected if some are missing
        existing_cols = [c for c in column_order if c in df.columns]

        # Reorder and save
        df[existing_cols].to_csv(filename, index=False, encoding="utf-8")
        logger.info(f"Successfully saved products CSV to {filename}")
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")
