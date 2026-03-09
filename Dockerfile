FROM python:3.14-slim AS builder

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

FROM python:3.14-slim

WORKDIR /app

RUN useradd --create-home appuser

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY main.py ./
COPY digitaltwin/ ./digitaltwin/
COPY specs/ ./specs/

USER appuser

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
