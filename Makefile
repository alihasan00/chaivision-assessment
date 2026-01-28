.PHONY: install run scrape index compare serve clean

VENV_DIR = .venv
PYTHON = $(VENV_DIR)/bin/python

# Default parameters
KEYWORD ?= massage gun
LIMIT ?= 10

# Install dependencies and setup virtual environment
install:
	test -d $(VENV_DIR) || python3 -m venv $(VENV_DIR)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# Run the FastAPI server
serve:
	$(PYTHON) -m uvicorn bot.app:app --reload --host 0.0.0.0 --port 8000

# Alias for run -> serve
run: serve

# Run the CLI scraper
# Usage: make scrape KEYWORD="walking pad" LIMIT=5
scrape:
	$(PYTHON) -m scrape.scrape --q "$(KEYWORD)" --n $(LIMIT)

# Run the indexer to build the vector store
# Usage: make index REBUILD=--rebuild (optional)
index:
	$(PYTHON) -m bot.indexer $(REBUILD)

# Run the comparison script
compare:
	$(PYTHON) analysis/compare.py

clean:
	rm -rf __pycache__
	rm -rf $(VENV_DIR)
