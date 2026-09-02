FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.deploy.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.deploy.txt

COPY . .

RUN python -m py_compile \
    app/main.py \
    app/llm/openai_client.py \
    app/llm/mock_client.py \
    app/llm/demo_resilient_client.py \
    app/llm/factory.py

CMD ["python", "-m", "scripts.start_prod"]
