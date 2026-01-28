import pandas as pd
import re
import argparse
from pathlib import Path


import sys
import os
from dotenv import load_dotenv

# Add project root to path so we can import from bot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.qwen_service import QwenService

load_dotenv()


def clean_price(price_str):
    if not isinstance(price_str, str):
        return None
    cleaned = re.sub(r"[^\d.]", "", price_str)
    try:
        return float(cleaned)
    except ValueError:
        return None


def clean_rating(rating_str):
    if not isinstance(rating_str, str):
        return None
    match = re.search(r"(\d+(\.\d+)?)", rating_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def clean_review_count(review_str):
    if not isinstance(review_str, str):
        return None
    cleaned = re.sub(r"[^\d]", "", review_str)
    try:
        return int(cleaned)
    except ValueError:
        return None


# AI extraction logic moved to bot.qwen_service.QwenService.extract_product_features


def build_feature_matrix(
    input_file="data/products.jsonl", output_file="data/feature_matrix.csv"
):
    print(f"Loading data from {input_file}...")
    try:
        if input_file.endswith(".jsonl"):
            df = pd.read_json(input_file, lines=True)
        else:
            df = pd.read_csv(input_file)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    print("Cleaning and processing data...")

    # Initialize Qwen service
    try:
        qwen = QwenService()
    except Exception as e:
        print(
            f"Warning: Could not initialize QwenService. AI features will be empty. Error: {e}"
        )
        qwen = None

    df["price_clean"] = df["price"].apply(clean_price)
    df["rating_clean"] = df["rating"].apply(clean_rating)
    df["reviews_clean"] = df["review_count"].apply(clean_review_count)
    # Remove old manual cleaning for dimensions/weight since AI handles it
    # df["dimensions_clean"] = df["dimensions"].apply(clean_dimensions)
    # df["weight_clean"] = df["weight"].apply(clean_weight)

    def combine_text(row):
        bullets = row.get("bullet_features", [])
        if isinstance(bullets, list):
            bullets = " ".join(bullets)
        elif not isinstance(bullets, str):
            bullets = ""
        # Include explicit dimensions/weight in text for AI to see if present in metadata
        meta_dims = row.get("dimensions", "")
        meta_weight = row.get("weight", "")
        return f"{row.get('title', '')} {bullets} Dimensions: {meta_dims} Weight: {meta_weight}"

    df["full_text"] = df.apply(combine_text, axis=1)

    print("Extracting features with AI (this may take a moment)...")
    print("Extracting features with AI (this may take a moment)...")
    if qwen:
        extracted_features = (
            df["full_text"]
            .apply(lambda x: qwen.extract_product_features(x))
            .apply(pd.Series)
        )
    else:
        extracted_features = pd.DataFrame()

    # Drop original dimensions/weight if present to avoid duplicates with AI extraction
    # The AI extraction already sees these values via combine_text
    columns_to_drop = [c for c in ["dimensions", "weight"] if c in df.columns]
    if columns_to_drop:
        df = df.drop(columns=columns_to_drop)

    df = pd.concat([df, extracted_features], axis=1)

    cols = [
        "asin",
        "title",
        "price_clean",
        "rating_clean",
        "reviews_clean",
        "brand",
        "dimensions",  # From AI
        "weight",  # From AI
        "battery_life",
        "noise_level",
        "attachments_count",
        "warranty",
        "voltage",
        "wattage",
    ]

    # Ensure columns exist even if not extracted
    for c in cols:
        if c not in df.columns:
            df[c] = None

    matrix = df[cols].copy()
    rename_map = {
        "price_clean": "price_usd",
        "rating_clean": "rating_stars",
        "reviews_clean": "review_count_num",
        # dimensions/weight keys from AI response map directly
    }
    matrix = matrix.rename(columns=rename_map)

    print(f"Saving feature matrix to {output_file}...")
    matrix.to_csv(output_file, index=False)
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate feature comparison matrix")
    parser.add_argument(
        "--input", default="data/products.jsonl", help="Input products file"
    )
    parser.add_argument(
        "--output", default="data/feature_matrix.csv", help="Output matrix file"
    )
    args = parser.parse_args()

    build_feature_matrix(args.input, args.output)
