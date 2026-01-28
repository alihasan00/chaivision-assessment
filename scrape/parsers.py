import re
from bs4 import BeautifulSoup
from bot.schemas import Product
from config import settings


def _clean_text(text):
    if not text:
        return None
    text = text.replace("\u200e", "").replace("\u200f", "")
    return " ".join(text.split()).strip()


def extract_title(soup):
    title_el = soup.select_one(settings.title_selector)
    return _clean_text(title_el.get_text()) if title_el else None


def extract_asin(soup, url):
    asin_match = re.search(settings.asin_pattern, url)
    if asin_match:
        return asin_match.group(1)
    asin_el = soup.select_one(settings.asin_input_selector)
    return asin_el.get("value") if asin_el else None


def extract_price(soup):
    for selector in settings.price_selectors:
        price_el = soup.select_one(selector)
        if price_el and (price_text := price_el.get_text()):
            return _clean_text(price_text)
    return None


def extract_rating(soup):
    for selector in settings.rating_selectors:
        rating_el = soup.select_one(selector)
        if rating_el:
            return _clean_text(rating_el.get_text())
    return None


def extract_review_count(soup):
    review_el = soup.select_one(settings.review_count_selector)
    return _clean_text(review_el.get_text()) if review_el else None


def extract_bullets(soup):
    bullets = soup.select(settings.bullets_selector)
    return [_clean_text(b.get_text()) for b in bullets if b.get_text().strip()]


def extract_brand(soup):
    brand_el = soup.select_one(settings.brand_selector)
    if not brand_el:
        return None
    text = _clean_text(brand_el.get_text())
    text = re.sub(settings.brand_cleanup_pattern, "", text, flags=re.IGNORECASE)
    text = text.replace("Visit the ", "").replace(" Store", "").strip()
    return text


def extract_image(soup):
    img_el = soup.select_one(settings.image_selector)
    return img_el.get("src") if img_el else None


def extract_breadcrumbs(soup):
    breadcrumb_els = soup.select(settings.breadcrumbs_selector)
    return [_clean_text(b.get_text()) for b in breadcrumb_els if b.get_text().strip()]


def extract_dimensions_and_weight(soup):
    tables = soup.select(settings.dimensions_selectors)
    dims = None
    weight = None

    for table in tables:
        rows = table.select("tr, li, .a-list-item")
        for row in rows:
            text = _clean_text(row.get_text())
            if not text:
                continue

            text_lower = text.lower()

            if "dimension" in text_lower or "size" in text_lower:
                val = re.sub(
                    settings.dimension_patterns[0],
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
                if ";" in val:
                    parts = val.split(";")
                    val = parts[0].strip()
                    for p in parts[1:]:
                        if any(u in p.lower() for u in settings.weight_units):
                            weight = p.strip()
                dims = val

            if "weight" in text_lower and not weight:
                val = re.sub(
                    settings.dimension_patterns[1],
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


def extract_search_results(html, n=None):
    soup = BeautifulSoup(html, "lxml")
    elements = soup.select(settings.search_result_selector)

    products = []
    for element in elements[:n] if n else elements:
        link = element.select_one(settings.product_link_selector)
        if link and (href := link.get("href")):
            full_url = (
                f"{settings.amazon_base_url}{href}"
                if href.startswith("/")
                else href
            )
            products.append({"url": full_url})

    return products
