import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import uvicorn

app = FastAPI()

# --- 設定の読み込み ---
RAW_STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/data")
STORAGE_ROOT = Path(RAW_STORAGE_ROOT).resolve()

@app.get("/{file_path:path}")
async def serve_file(file_path: str):
    # 1. 物理パス構築
    requested_path = (STORAGE_ROOT / file_path).resolve()

    # 2. セキュリティチェック
    try:
        if not requested_path.is_relative_to(STORAGE_ROOT):
            raise HTTPException(status_code=403, detail="Forbidden")
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    # 3. 存在確認
    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404)

    # 4. xattr からメタデータ取得
    headers = {"X-Content-Type-Options": "nosniff"}
    try:
        mime_type = os.getxattr(requested_path, "user.user.content-type").decode('utf-8')
        try:
            headers["Cache-Control"] = os.getxattr(requested_path, "user.user.cache-control").decode('utf-8')
        except OSError:
            headers["Cache-Control"] = "max-age=31536000, immutable"
        try:
            headers["Content-Disposition"] = os.getxattr(requested_path, "user.user.content-disposition").decode('utf-8')
        except OSError:
            headers["Content-Disposition"] = "inline"
    except OSError:
        mime_type = "application/octet-stream"
        headers["Cache-Control"] = "no-cache"

    return FileResponse(path=requested_path, media_type=mime_type, headers=headers)

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "80"))
    workers = int(os.getenv("WORKERS", "4"))
    uds_path = os.getenv("UDS_PATH") # 例: /tmp/uvicorn.sock

    config = {
        "app": "main:app",
        "workers": workers,
        "proxy_headers": True,
        "forwarded_allow_ips": "*"
    }

    if uds_path:
        # --- Unix Domain Socket モード ---
        # 既存のソケットファイルがある場合は削除
        if os.path.exists(uds_path):
            os.remove(uds_path)
        
        print(f"--- Starting FastAPI on UDS: {uds_path} ---")
        uvicorn.run(**config, uds=uds_path)
    else:
        # --- TCP モード ---
        print(f"--- Starting FastAPI on TCP: {host}:{port} ---")
        uvicorn.run(**config, host=host, port=port)