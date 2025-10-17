release: uv sync --frozen
web: uv run gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app