# Amazon Top-10 Intelligence (Keyword Edition)

This tool scrapes the top 10 Amazon products for a given keyword, builds a comparison table, and exposes a Q&A API using Qwen API and a local vector store.

## Features

- **Scrape Service**: Collects top-10 Amazon products and details.
- **Feature Comparison**: Generates a CSV matrix from scraped data.
- **Q&A API**: FastAPI app backed by Qwen API and RAG (Retrieval-Augmented Generation) on product data.

## Setup

1.  **Clone the repository** (if you haven't already).

2.  **Create a `.env` file** in the root directory:
    ```bash
    cp .env.example .env
    ```
    
    Edit `.env` and populate your API keys:
    ```
    QWEN_API_KEY=sk-your-qwen-key
    ZYTE_API_KEY=your-zyte-key
    ```
    
    **Required:**
    - `QWEN_API_KEY`: Your Qwen API key (required for Q&A functionality and feature extraction)
    - `ZYTE_API_KEY`: Your Zyte API key (required for live scraping)

3.  **Install dependencies**:
    ```bash
    make install
    ```

## Usage

### 1. CLI Scraper

Run the scraper to fetch data for a specific keyword.

```bash
python scrape/scrape.py --q "massage gun" --n 10
```

**Using Makefile:**
```bash
make scrape KEYWORD="massage gun" LIMIT=10
```

*   `--q` / `KEYWORD`: Search keyword (required).
*   `--n` / `LIMIT`: Number of products (default: 10).

### 2. Compare Features

Generate a feature matrix CSV with AI-extracted features:

```bash
python analysis/compare.py
```

**Using Makefile:**
```bash
make compare
```

This produces `data/feature_matrix.csv`.

### 3. Index Data

After scraping, build the vector index for the chatbot:

```bash
make index
```

To rebuild an existing index:

```bash
make index REBUILD=--rebuild
```

### 4. Run API Server

Start the FastAPI server to expose endpoints:

```bash
uvicorn bot.app:app --reload
```

**Using Makefile:**
```bash
make serve
```
(Or `make run`)

The API will be available at `http://localhost:8000`.
- **Docs**: `http://localhost:8000/docs`

## API Endpoints

### POST /scrape

Scrape top N Amazon products by keyword.

**Request:**
```json
{
  "keyword": "massage gun",
  "n": 10
}
```

**Response:**
```json
{
  "ok": true,
  "count": 10,
  "message": "Successfully scraped 10 products for keyword 'massage gun'"
}
```

**Example with curl:**
```bash
curl -X POST "http://localhost:8000/scrape" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "massage gun", "n": 10}'
```

### POST /index

Rebuild vector index from products.jsonl.

**Request:**
```json
{
  "input_file": "data/products.jsonl",
  "rebuild": true
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Successfully indexed 10 products from data/products.jsonl",
  "products_indexed": 10
}
```

**Example with curl:**
```bash
curl -X POST "http://localhost:8000/index" \
  -H "Content-Type: application/json" \
  -d '{"input_file": "data/products.jsonl", "rebuild": true}'
```

### POST /ask

Ask questions about scraped products using RAG (Retrieval-Augmented Generation).

**Request:**
```json
{
  "question": "Which model under $100 has the best rating?",
  "k": 5
}
```

**Response:**
```json
{
  "answer": "Model X (ASIN: B0...) is highest-rated under $100 with 4.6★ from 8k+ reviews.",
  "sources": [
    {
      "asin": "B0XXXX",
      "title": "Product Title",
      "brand": "Brand Name",
      "price": "$89.99",
      "rating": "4.6",
      "review_count": "8,234",
      "breadcrumbs": "Electronics > Health & Personal Care",
      "dimensions": "10 x 5 x 3 inches",
      "weight": "2.5 pounds",
      "url": "https://amazon.com/...",
      "image_url": "https://..."
    },
    {
      "asin": "B0YYYY",
      "title": "Another Product",
      "brand": "Another Brand",
      "price": "$79.99",
      "rating": "4.5",
      "review_count": "5,123",
      "breadcrumbs": "Electronics > Health & Personal Care",
      "dimensions": "9 x 4 x 2 inches",
      "weight": "2.0 pounds",
      "url": "https://amazon.com/...",
      "image_url": "https://..."
    }
  ],
  "num_sources": 2
}
```

**Example with curl:**
```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Which model under $100 has the best rating?", "k": 5}'
```

**Parameters:**
- `question` (required): The question to ask about the products
- `k` (optional, default: 5): Number of relevant products to retrieve for context

## Assumptions

This project makes the following assumptions and design decisions:

1. **Amazon Anti-Bot Measures**: The scraper uses Zyte API to handle Amazon's anti-bot measures. Zyte provides proxy services and browser automation to reliably scrape Amazon product pages while respecting rate limits and avoiding blocks.

2. **Local-Only Deployment**: This is designed for local development and testing only. No cloud deployment is required or expected. All data (products, CSVs, vector indices) is stored locally in the `data/` directory.

3. **Qwen API Requirement**: The Q&A functionality requires a valid Qwen API key. This must be provided via the `QWEN_API_KEY` environment variable in your `.env` file. The system uses Qwen API for both question answering and feature extraction.

4. **Vector Store**: The project uses Chroma as the local vector store (FAISS is also supported per requirements). The vector index is built from scraped product data and persisted locally in the `data/` directory.

5. **Data Format**: Scraped products are stored in JSONL format (`data/products.jsonl`) with one product per line. CSV exports (`data/products.csv` and `data/feature_matrix.csv`) are generated for analysis and comparison.

6. **Zyte API**: The system uses Zyte API exclusively for scraping Amazon product pages. A valid `ZYTE_API_KEY` is required in the `.env` file for the scraper to function.

## Project Structure

- `config/`: Configuration and shared utilities.
  - `settings.py`: Pydantic settings for all configuration values
  - `logger.py`: Centralized logging configuration
  - `prompts.py`: AI prompt templates
- `scrape/`: Scraping logic (fetcher, parsers, CLI).
  - `fetcher.py`: Zyte API integration for HTTP fetch with polite backoff
  - `parsers.py`: Selectors and data normalizers
  - `scrape.py`: CLI entrypoint
  - `exporter.py`: Export functions for JSONL and CSV
- `bot/`: Chatbot logic (indexing, FastAPI app, Qwen integration).
  - `indexer.py`: Builds vector store from products.jsonl
  - `app.py`: FastAPI app with `/scrape`, `/index`, and `/ask` endpoints
  - `qwen_service.py`: Qwen API integration for question answering
  - `schemas.py`: Pydantic models for API requests/responses
  - `utils.py`: Utility functions for dependency injection
- `analysis/`: Feature comparison and analysis.
  - `compare.py`: Builds feature_matrix.csv from products.jsonl
- `data/`: Stores scraped JSONL, CSVs, and vector DB.
  - `products.jsonl`: Scraped product data (one JSON object per line)
  - `products.csv`: CSV export of scraped products
  - `feature_matrix.csv`: AI-extracted feature comparison matrix
  - `chroma_db/`: ChromaDB vector store persistence directory

## Test Keywords

The system has been tested with the following keywords:
- "massage gun"
- "walking pad"
- "monitor light bar"

Your system should handle any keyword, produce fresh `products.jsonl`/`products.csv`, rebuild the index, and answer grounded questions with cited ASINs and product information.
