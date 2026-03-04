# --- ビルドステージ ---
FROM python:3.12-slim AS builder

WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 実行ステージ ---
FROM python:3.12-slim

# 1. appuser を UID/GID 101 で作成
RUN groupadd -g 101 appuser && \
    useradd -u 101 -g 101 -r -s /bin/false appuser

WORKDIR /app

# ビルダーからライブラリをコピー
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# アプリケーションコードをコピー
COPY main.py requirements.txt ./

# 2. 指定のディレクトリ作成と権限変更
# /data: ストレージ用 (読み取り専用アクセス)
# /var/run/s3proxy-deliverer: UDS ソケット用 (書き込み必要)
RUN mkdir -p /data /var/run/s3proxy-deliverer && \
    chown root:appuser /data && chmod 750 /data && \
    chown appuser:appuser /app /var/run/s3proxy-deliverer

EXPOSE 80

# 環境変数の設定
ENV STORAGE_ROOT=/data \
    WORKERS=4 \
    PORT=80 \
    UDS_PATH=/var/run/s3proxy-deliverer/uvicorn.sock \
    PYTHONUNBUFFERED=1

# ユーザーを切り替え
USER appuser

# アプリケーションの起動
CMD ["python", "main.py"]