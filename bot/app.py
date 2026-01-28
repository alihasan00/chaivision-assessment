from fastapi import FastAPI, HTTPException, Depends
from scrape.fetcher import scrape_products
from scrape.logger import get_logger
from bot.schemas import (
    ScrapeRequest,
    ScrapeResponse,
    AskRequest,
    AskResponse,
    IndexRequest,
    IndexResponse,
)
from bot.utils import get_indexer, get_qwen_service, clear_indexer_cache
from bot.indexer import ProductIndexer
from bot.qwen_service import QwenService
from pathlib import Path
from langchain_chroma import Chroma

logger = get_logger(__name__)

app = FastAPI(
    title="Amazon Top-10 Intelligence API",
    description="Scrape and analyze top Amazon products by keyword",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Amazon Top-10 Intelligence API is running",
        "endpoints": {
            "POST /scrape": "Scrape top N Amazon products by keyword",
            "POST /index": "Rebuild vector index from products.jsonl",
            "POST /ask": "Ask questions about scraped products (hybrid search + Qwen)",
        },
    }


@app.post("/scrape", response_model=ScrapeResponse)
async def api_scrape_products(request: ScrapeRequest):
    try:
        logger.info(
            f"Received scrape request: keyword='{request.keyword}', n={request.n}, use_local_html={request.use_local_html}"
        )

        products = await scrape_products(
            query=request.keyword,
            n=request.n,
            use_local_html=request.use_local_html,
        )

        if not products:
            raise HTTPException(
                status_code=500,
                detail="Failed to scrape products. Check logs for details.",
            )

        logger.info(f"Successfully scraped {len(products)} products")

        return ScrapeResponse(
            ok=True,
            count=len(products),
            message=f"Successfully scraped {len(products)} products for keyword '{request.keyword}'",
        )

    except Exception as e:
        logger.error(f"Error in scrape endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index", response_model=IndexResponse)
async def rebuild_index(request: IndexRequest = IndexRequest()):
    try:
        logger.info(
            f"Received index request: input_file='{request.input_file}', rebuild={request.rebuild}"
        )

        input_path = Path(request.input_file)
        if not input_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Input file not found: {request.input_file}",
            )

        indexer = ProductIndexer()

        if request.rebuild:
            persist_path = Path(indexer.persist_directory)
            if persist_path.exists():
                logger.info(f"Deleting existing collection at {indexer.persist_directory}...")
                try:
                    db = Chroma(
                        persist_directory=indexer.persist_directory,
                        embedding_function=indexer.embeddings,
                    )
                    db.delete_collection()
                    logger.info("Existing collection deleted successfully")
                except Exception as e:
                    logger.warning(f"Failed to delete collection (might not exist): {e}")

        products = indexer.load_products(request.input_file)
        if not products:
            raise HTTPException(
                status_code=400,
                detail=f"No products found in {request.input_file}",
            )

        indexer.build_index(products)

        clear_indexer_cache()

        logger.info(f"Successfully indexed {len(products)} products")

        return IndexResponse(
            ok=True,
            message=f"Successfully indexed {len(products)} products from {request.input_file}",
            products_indexed=len(products),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in index endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    indexer: ProductIndexer = Depends(get_indexer),
    qwen_service: QwenService = Depends(get_qwen_service),
):
    try:
        logger.info(f"Received question: '{request.question}'")

        documents = indexer.search(
            query=request.question,
            k=request.k,
        )

        if not documents:
            return AskResponse(
                answer="I couldn't find any relevant products to answer your question.",
                sources=[],
                num_sources=0,
            )

        result = qwen_service.answer_question(
            question=request.question,
            documents=documents,
        )

        return AskResponse(
            answer=result.answer,
            sources=result.sources,
            num_sources=result.num_sources,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
