uv-install:
	uv venv
	source .venv/bin/activate
	uv sync
	uv pip install -e .

all:
	uv run scripts/1

