from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScrapeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    zyte_api_key: str = ""
    zyte_api_url: str = "https://api.zyte.com/v1/extract"
    zyte_timeout: float = 180.0
    zyte_max_retries: int = 3
    zyte_wait_timeout: int = 5
    zyte_geolocation: str = "US"
    zyte_device: str = "desktop"
    zyte_session_hash_mod: int = 1000

    amazon_base_url: str = "https://www.amazon.com"
    amazon_search_path: str = "/s?k="

    html_snapshots_dir: str = "html_snapshots"
    data_dir: str = "data"
    products_jsonl: str = "data/products.jsonl"
    products_csv: str = "data/products.csv"

    default_product_limit: int = 10
    product_delay_seconds: float = 2.0
    retry_backoff_base: int = 2
    retry_backoff_multiplier: int = 2

    search_result_selector: str = 'div[data-component-type="s-search-result"]'
    product_link_selector: str = "a.a-link-normal"

    price_selectors: list[str] = [
        ".a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".a-price-whole",
    ]

    title_selector: str = "#productTitle"
    asin_input_selector: str = 'input[name="ASIN"]'
    rating_selectors: list[str] = [
        'span[data-hook="rating-out-of-text"]',
        "i.a-icon-star span",
    ]
    review_count_selector: str = "#acrCustomerReviewText"
    bullets_selector: str = "#feature-bullets ul li span.a-list-item"
    brand_selector: str = "#bylineInfo"
    image_selector: str = "#landingImage"
    breadcrumbs_selector: str = "#wayfinding-breadcrumbs_feature_div ul li a"
    dimensions_selectors: str = (
        "table.prodDetTable, #productDetails_techSpec_section_1, "
        "#detailBullets_feature_div, #productOverview_feature_div"
    )

    asin_pattern: str = r"/dp/([A-Z0-9]{10})"
    brand_cleanup_pattern: str = r"^Brand:\s*"
    dimension_patterns: list[str] = [
        r"^(Product Dimensions|Item Dimensions|Dimensions|Size|Item Display Dimensions)\s*[:\s]*",
        r"^(Item Weight|Product Weight|Package Weight|Weight)\s*[:\s]*",
    ]
    weight_units: list[str] = ["ounce", "pound", "kg", "g", "lb", "oz"]

    csv_column_order: list[str] = [
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
    csv_list_columns: list[str] = ["bullet_features", "breadcrumbs"]


@lru_cache(maxsize=None)
def get_scrape_settings() -> ScrapeSettings:
    return ScrapeSettings()


settings = get_scrape_settings()
