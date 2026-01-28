from functools import lru_cache
from fastapi import HTTPException
from bot.indexer import ProductIndexer
from bot.qwen_service import QwenService
from scrape.logger import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_indexer() -> ProductIndexer:
    logger.info("Initializing ProductIndexer...")
    indexer = ProductIndexer()
    try:
        indexer.load_index()
    except Exception as e:
        logger.error(f"Failed to load index: {e}")
        raise HTTPException(
            status_code=503,
            detail="Search index not available. Please build the index first using: python -m bot.indexer",
        )
    return indexer


def clear_indexer_cache():
    get_indexer.cache_clear()
    logger.info("Indexer cache cleared")


@lru_cache()
def get_qwen_service() -> QwenService:
    logger.info("Initializing QwenService...")
    try:
        return QwenService()
    except ValueError as e:
        logger.error(f"Failed to initialize Qwen service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Qwen service not available. Please set QWEN_API_KEY in .env file.",
        )
