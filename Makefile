.PHONY: install chat dashboard voice telegram brief lint test gate

install:
	uv venv && uv pip install -e .

chat:
	uv run luci

dashboard:
	uv run luci dashboard

voice:
	uv pip install -e '.[voice]' && uv run luci voice

telegram:
	uv run luci telegram

brief:
	uv run luci brief

lint:
	uv run ruff check luci/ && uv run ruff format --check luci/

test:
	uv run pytest evals/deterministic/ -v

gate:
	uv pip install -e '.[eval]' && uv run pytest evals/ -v
