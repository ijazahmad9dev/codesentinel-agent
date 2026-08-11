FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data \
    && useradd --create-home --uid 1000 sentinel \
    && chown -R sentinel:sentinel /app

USER sentinel

CMD ["python", "-m", "src.main"]