.PHONY: demo test doctor lint bootstrap tunnel

demo:
	./scripts/bootstrap.sh --demo

bootstrap:
	./scripts/bootstrap.sh

test:
	uv run pytest tests -q

doctor:
	uv run thekedar doctor

lint:
	uv run ruff check packages tests

init:
	uv run thekedar init --yes --mode local-demo

tunnel:
	./scripts/tunnel.sh

demo-message:
	./scripts/send-demo-message.sh
