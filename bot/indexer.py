import json
import argparse
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from config import get_logger
from bot.schemas import Product

load_dotenv()
logger = get_logger(__name__)


class ProductIndexer:
    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        embedding_model: str = "text-embedding-v4",
    ):
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            raise ValueError("QWEN_API_KEY not found in environment variables")

        self.persist_directory = persist_directory
        self.embedding_model = embedding_model

        # Use OpenAI embeddings wrapper for DashScope compatibility
        # This ensures we use the correct base_url matches main.py

        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            api_key=api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            check_embedding_ctx_length=False,
        )
        self.vector_store = None
        self.documents = []

    def load_products(self, input_file: str = "data/products.jsonl") -> List[Product]:
        logger.info(f"Loading products from {input_file}")
        products = []

        with open(input_file, "r", encoding="utf-8") as f:
            # Try loading as a standard JSON array first
            try:
                content = json.load(f)
                if isinstance(content, list):
                    logger.info(f"Loaded {len(content)} products from JSON array")
                    for item in content:
                        try:
                            products.append(Product.model_validate(item))
                        except Exception as e:
                            logger.warning(f"Skipping invalid product: {e}")
                            continue
                    return products
            except json.JSONDecodeError:
                f.seek(0)
                pass

            # Reset file pointer and read line by line (JSONL)
            f.seek(0)
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        products.append(Product.model_validate(data))
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping invalid JSON line in {input_file}")
                        continue
                    except Exception as e:
                        logger.warning(f"Skipping invalid product: {e}")
                        continue

        logger.info(f"Loaded {len(products)} products")
        return products

    def _product_to_text(self, product: Product) -> str:
        parts = []

        fields = [
            ("ASIN", product.asin),
            ("Title", product.title),
            ("Brand", product.brand),
            ("Price", product.price),
            ("Rating", product.rating),
            ("Reviews", product.review_count),
            ("Dimensions", product.dimensions),
            ("Weight", product.weight),
            ("URL", product.url),
            ("Image URL", product.image_url),
        ]

        for label, value in fields:
            if value:
                parts.append(f"{label}: {value}")

        if product.breadcrumbs:
            if isinstance(product.breadcrumbs, list):
                parts.append(f"Breadcrumbs: {' > '.join(product.breadcrumbs)}")
            else:
                parts.append(f"Breadcrumbs: {product.breadcrumbs}")

        if product.bullet_features:
            if isinstance(product.bullet_features, list):
                parts.append(f"Features: {' '.join(product.bullet_features)}")
            else:
                parts.append(f"Features: {product.bullet_features}")

        return "\n".join(parts)

    def build_index(self, products: List[Product]):
        logger.info("Building indexes...")

        self.documents = []
        for product in products:
            text = self._product_to_text(product)
            doc = Document(
                page_content=text,
                metadata={
                    "asin": product.asin or "",
                    "title": product.title or "",
                    "price": product.price or "",
                    "rating": product.rating or "",
                    "review_count": product.review_count or "",
                    "brand": product.brand or "",
                    "bullet_features": str(product.bullet_features) if product.bullet_features else "",
                    "breadcrumbs": str(product.breadcrumbs) if product.breadcrumbs else "",
                    "dimensions": product.dimensions or "",
                    "weight": product.weight or "",
                    "url": product.url or "",
                    "image_url": product.image_url or "",
                },
            )
            self.documents.append(doc)

        if not self.documents:
            logger.warning("No documents to index. Skipping vector store creation.")
            return

        logger.info("Building vector store with ChromaDB...")
        self.vector_store = Chroma.from_documents(
            documents=self.documents,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
        )

        logger.info("Vector index built successfully!")

    def load_index(self):
        logger.info("Loading existing index...")

        self.vector_store = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
        )

        logger.info("Vector index loaded successfully!")

    def search(
        self,
        query: str,
        k: int = 5,
    ) -> List[Document]:
        if not self.vector_store:
            raise ValueError(
                "Indexes not loaded. Call build_index() or load_index() first."
            )

        logger.info(f"Searching for '{query}' with k={k}")
        results = self.vector_store.similarity_search(query, k=k)

        logger.info(f"Search returned {len(results)} results")
        return results


def main():
    parser = argparse.ArgumentParser(description="Build product search index")
    parser.add_argument(
        "--input",
        default="data/products.jsonl",
        help="Input products file (JSONL)",
    )
    parser.add_argument(
        "--persist-dir",
        default="data/chroma_db",
        help="Directory to persist ChromaDB",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild index even if it exists",
    )
    args = parser.parse_args()

    indexer = ProductIndexer(persist_directory=args.persist_dir)

    persist_path = Path(args.persist_dir)
    if persist_path.exists() and not args.rebuild:
        logger.info("Index already exists. Use --rebuild to recreate.")
        return

    if args.rebuild and persist_path.exists():
        logger.info(f"Resetting existing collection at {args.persist_dir}...")
        db = Chroma(
            persist_directory=args.persist_dir,
            embedding_function=indexer.embeddings,
        )
        try:
            db.delete_collection()
            logger.info("Collection deleted.")
        except Exception as e:
            logger.warning(f"Failed to delete collection (might not exist): {e}")

    products = indexer.load_products(args.input)
    if not products:
        logger.error(f"No products found in {args.input}. Please scrape products first.")
        return

    indexer.build_index(products)

    logger.info(f"Index saved to {args.persist_dir}")


if __name__ == "__main__":
    main()
