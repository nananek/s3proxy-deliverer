FROM python:3.11-slim

RUN pip install --no-cache-dir fastapi uvicorn

# アプリケーションコードのコピー
COPY main.py /app/main.py

WORKDIR /app

# uvicornで起動 (ポート80)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
