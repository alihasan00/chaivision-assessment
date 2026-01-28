from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class ScrapeRequest(BaseModel):
    keyword: str
    n: int = 10
    use_local_html: bool = False


class ScrapeResponse(BaseModel):
    ok: bool
    count: int
    message: str = ""


class AskRequest(BaseModel):
    question: str
    k: int = 5


class Product(BaseModel):
    """Product model representing scraped Amazon product data.
    All fields are optional since scraped data can be empty or incomplete.
    """
    model_config = ConfigDict(extra="ignore")
    
    asin: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[str] = None
    rating: Optional[str] = None
    review_count: Optional[str] = None
    bullet_features: Optional[List[str]] = None
    breadcrumbs: Optional[List[str]] = None
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None


class ProductSource(BaseModel):
    asin: str
    title: str
    brand: str
    price: str
    rating: str
    review_count: str
    breadcrumbs: str
    dimensions: str
    weight: str
    url: str
    image_url: str


class AskResponse(BaseModel):
    answer: str
    sources: List[ProductSource]
    num_sources: int


class IndexRequest(BaseModel):
    input_file: str = "data/products.jsonl"
    rebuild: bool = True


class IndexResponse(BaseModel):
    ok: bool
    message: str
    products_indexed: int


class QwenAnswerResponse(BaseModel):
    """Response model for QwenService.answer_question()"""
    answer: str
    sources: List[ProductSource]
    num_sources: int
