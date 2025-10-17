release: python -m uv sync --frozen
web: python -m uv run gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.main:app