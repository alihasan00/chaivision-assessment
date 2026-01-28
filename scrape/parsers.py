import re
from bs4 import BeautifulSoup
from bot.schemas import Product

PRICE_SELECTORS = [
    ".a-price .a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price-whole",
]


def _clean_text(text):
    if not text:
        return None
    text = text.replace("\u200e", "").replace("\u200f", "")
    return " ".join(text.split()).strip()


def extract_title(soup):
    title_el = soup.select_one("#productTitle")
    return _clean_text(title_el.get_text()) if title_el else None


def extract_asin(soup, url):
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)

    asin_el = soup.select_one('input[name="ASIN"]')
    return asin_el.get("value") if asin_el else None


def extract_price(soup):
    for selector in PRICE_SELECTORS:
        price_el = soup.select_one(selector)
        if price_el:
            price_text = price_el.get_text()
            if price_text:
                return _clean_text(price_text)
    return None


def extract_rating(soup):
    rating_el = soup.select_one('span[data-hook="rating-out-of-text"]')
    if not rating_el:
        rating_el = soup.select_one("i.a-icon-star span")
    return _clean_text(rating_el.get_text()) if rating_el else None


def extract_review_count(soup):
    review_el = soup.select_one("#acrCustomerReviewText")
    return _clean_text(review_el.get_text()) if review_el else None


def extract_bullets(soup):
    bullets = soup.select("#feature-bullets ul li span.a-list-item")
    return [_clean_text(b.get_text()) for b in bullets if b.get_text().strip()]


def extract_brand(soup):
    brand_el = soup.select_one("#bylineInfo")
    if brand_el:
        text = _clean_text(brand_el.get_text())
        text = re.sub(r"^Brand:\s*", "", text, flags=re.IGNORECASE)
        text = text.replace("Visit the ", "").replace(" Store", "").strip()
        return text
    return None


def extract_image(soup):
    img_el = soup.select_one("#landingImage")
    return img_el.get("src") if img_el else None


def extract_breadcrumbs(soup):
    breadcrumb_els = soup.select("#wayfinding-breadcrumbs_feature_div ul li a")
    return [_clean_text(b.get_text()) for b in breadcrumb_els if b.get_text().strip()]


def extract_dimensions_and_weight(soup):
    tables = soup.select(
        "table.prodDetTable, #productDetails_techSpec_section_1, #detailBullets_feature_div, #productOverview_feature_div"
    )
    dims = None
    weight = None

    for table in tables:
        # Added .a-list-item to support cases where data is in spans/divs not just tr/li
        rows = table.select("tr, li, .a-list-item")
        for row in rows:
            text = _clean_text(row.get_text())
            if not text:
                continue

            # Normalized text for easier matching
            text_lower = text.lower()

            if "dimension" in text_lower or "size" in text_lower:
                val = re.sub(
                    r"^(Product Dimensions|Item Dimensions|Dimensions|Size|Item Display Dimensions)\s*[:\s]*",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                if ";" in val:
                    parts = val.split(";")
                    val = parts[0].strip()
                    for p in parts[1:]:
                        if any(
                            u in p.lower()
                            for u in ["ounce", "pound", "kg", "g", "lb", "oz"]
                        ):
                            weight = p.strip()
                dims = val

            if "weight" in text_lower and not weight:
                val = re.sub(
                    r"^(Item Weight|Product Weight|Package Weight|Weight)\s*[:\s]*",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                weight = val

    return {"dims": dims, "weight": weight}


def extract_product_details(html, url) -> Product:
    soup = BeautifulSoup(html, "lxml")
    dims_weight = extract_dimensions_and_weight(soup)

    return Product(
        url=url,
        title=extract_title(soup),
        asin=extract_asin(soup, url),
        price=extract_price(soup),
        rating=extract_rating(soup),
        review_count=extract_review_count(soup),
        bullet_features=extract_bullets(soup),
        brand=extract_brand(soup),
        image_url=extract_image(soup),
        breadcrumbs=extract_breadcrumbs(soup),
        dimensions=dims_weight.get("dims"),
        weight=dims_weight.get("weight"),
    )


def extract_search_results(html):
    soup = BeautifulSoup(html, "lxml")
    elements = soup.select('div[data-component-type="s-search-result"]')

    products = []
    for element in elements[:10]:
        link = element.select_one("a.a-link-normal")
        if link and link.get("href"):
            href = link.get("href")
            full_url = f"https://www.amazon.com{href}" if href.startswith("/") else href
            products.append({"url": full_url})

    return products
