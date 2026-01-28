from typing import List
import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.documents import Document
from scrape.logger import get_logger
from bot.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    PRODUCT_CONTEXT_TEMPLATE,
    FEATURE_EXTRACTION_PROMPT,
)
from bot.schemas import QwenAnswerResponse, ProductSource
import json

load_dotenv()
logger = get_logger(__name__)


class QwenService:
    def __init__(self, model: str = "qwen-plus"):
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            raise ValueError("QWEN_API_KEY not found in environment variables")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model

    def _format_context(self, documents: List[Document]) -> str:
        if not documents:
            return "No relevant products found."

        formatted_docs = []
        for i, doc in enumerate(documents, 1):
            metadata = doc.metadata
            doc_str = PRODUCT_CONTEXT_TEMPLATE.format(
                index=i,
                asin=metadata.get("asin", "N/A"),
                title=metadata.get("title", "N/A"),
                brand=metadata.get("brand", "N/A"),
                price=metadata.get("price", "N/A"),
                rating=metadata.get("rating", "N/A"),
                content=doc.page_content,
            )
            formatted_docs.append(doc_str)

        return "\n\n".join(formatted_docs)

    def answer_question(
        self,
        question: str,
        documents: List[Document],
    ) -> QwenAnswerResponse:
        logger.info(f"Answering question: {question}")

        context = self._format_context(documents)

        # Construct the user message using the template
        user_content = USER_PROMPT_TEMPLATE.format(question=question, context=context)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )

            answer = response.choices[0].message.content

            sources = [
                ProductSource(
                    asin=doc.metadata.get("asin", ""),
                    title=doc.metadata.get("title", ""),
                    brand=doc.metadata.get("brand", ""),
                    price=doc.metadata.get("price", ""),
                    rating=doc.metadata.get("rating", ""),
                    review_count=doc.metadata.get("review_count", ""),
                    breadcrumbs=doc.metadata.get("breadcrumbs", ""),
                    dimensions=doc.metadata.get("dimensions", ""),
                    weight=doc.metadata.get("weight", ""),
                    url=doc.metadata.get("url", ""),
                    image_url=doc.metadata.get("image_url", ""),
                )
                for doc in documents
            ]

            logger.info(f"Generated answer with {len(sources)} sources")

            return QwenAnswerResponse(
                answer=answer,
                sources=sources,
                num_sources=len(sources),
            )

        except Exception as e:
            logger.error(f"Error calling Qwen API via OpenAI SDK: {e}")
            raise

    def extract_product_features(self, text: str) -> dict:
        """
        Extracts technical features from product text using Qwen.
        Returns a dictionary of features.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": FEATURE_EXTRACTION_PROMPT},
                    {"role": "user", "content": f"Product Text: {text}"},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return {}
