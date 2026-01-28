import json
from pathlib import Path

import pandas as pd

from config import get_logger, settings

logger = get_logger(__name__)


def save_to_jsonl(products, filename=None):
    filename = filename or settings.products_jsonl
    logger.info(f"Saving {len(products)} products to {filename}")
    try:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(products)
        df.to_json(
            filename, orient="records", lines=True, force_ascii=False, index=False
        )
        logger.info(f"Successfully saved JSONL to {filename}")
    except Exception as e:
        logger.error(f"Failed to save JSONL: {e}")


def save_to_csv(products, filename=None):
    filename = filename or settings.products_csv
    logger.info(f"Saving products CSV to {filename}")
    try:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(products)

        for col in settings.csv_list_columns:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: json.dumps(x) if isinstance(x, list) else x
                )

        existing_cols = [c for c in settings.csv_column_order if c in df.columns]
        df[existing_cols].to_csv(filename, index=False, encoding="utf-8")
        logger.info(f"Successfully saved products CSV to {filename}")
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")
