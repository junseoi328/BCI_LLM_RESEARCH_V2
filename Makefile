.PHONY: install test run validate eval ablation smoke

install:
	python -m pip install -r requirements.txt

test:
	python -m pytest -q

run:
	python -m uvicorn app.main:app --reload

validate:
	python -m scripts.validate_dataset

eval:
	python -m eval.run_eval --context-level full

ablation:
	python -m eval.run_ablation

smoke:
	python -m scripts.live_smoke_test
