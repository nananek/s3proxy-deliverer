import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI()

# コンテナ内のデータルート（docker-composeのボリュームマウント先に合わせる）
# .resolve() で起動時に絶対パスを確定させておきます
STORAGE_ROOT = Path("/data").resolve()

@app.get("/{file_path:path}")
async def serve_file(file_path: str):
    # 1. 物理パスの構築
    # リクエストされたパスとベースディレクトリを結合し、../ などを解決
    requested_path = (STORAGE_ROOT / file_path).resolve()

    # 2. ディレクトリトラバーサル対策 (セキュリティの要)
    # 解決後の絶対パスが、許可されたディレクトリ配下に収まっているかチェック
    try:
        if not requested_path.is_relative_to(STORAGE_ROOT):
            raise HTTPException(status_code=403, detail="Forbidden: Access denied")
    except ValueError:
        # 親子関係にないパス（別のボリュームを指そうとした等）の場合
        raise HTTPException(status_code=403, detail="Forbidden: Invalid path")

    # 3. ファイルの存在確認
    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # 4. xattr（拡張属性）からのメタデータ復元
    headers = {
        "X-Content-Type-Options": "nosniff", # MIMEタイプの誤認防止
    }
    
    try:
        # S3Proxyが書き込んだ各属性を読み取る
        # Pythonの os.getxattr は Linux環境で 'user.user.xxx' のように指定します
        mime_type = os.getxattr(requested_path, "user.user.content-type").decode('utf-8')
        
        # オプショナルな属性（存在しない可能性があるもの）の取得
        try:
            headers["Cache-Control"] = os.getxattr(requested_path, "user.user.cache-control").decode('utf-8')
        except OSError:
            headers["Cache-Control"] = "max-age=31536000, immutable" # デフォルト値

        try:
            headers["Content-Disposition"] = os.getxattr(requested_path, "user.user.content-disposition").decode('utf-8')
        except OSError:
            # 取得できない場合はインライン表示をデフォルトに
            headers["Content-Disposition"] = "inline"

    except OSError:
        # 万が一 mime-type すら取れない場合のフォールバック
        mime_type = "application/octet-stream"
        headers["Cache-Control"] = "no-cache"

    # 5. ファイル配信の実行
    # FileResponse は内部で aiofiles を使い、ノンブロッキングで動作します
    return FileResponse(
        path=requested_path,
        media_type=mime_type,
        headers=headers
    )

if __name__ == "__main__":
    import uvicorn
    # Dockerコンテナ内からのリクエストを受けるため 0.0.0.0 で待機
    uvicorn.run(app, host="0.0.0.0", port=80)
