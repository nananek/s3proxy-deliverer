# S3Proxy Deliverer

FastAPIベースの軽量なファイル配信サーバーです。ローカルストレージ内のファイルを配信する際、ファイルシステムの**拡張属性 (xattr)** を参照して HTTP レスポンスヘッダー（`Content-Type` や `Cache-Control`）を動的に設定できるのが特徴です。

## 🚀 主な機能

* **xattr によるメタデータ管理**: ファイルごとに `Content-Type` や `Cache-Control` を保持・出力可能。
* **Unix Domain Socket (UDS) 対応**: リバースプロキシ（Nginx等）との高速な通信が可能。
* **セキュリティ**: パストラバーサル対策済みのパス解決。
* **軽量・高速**: Python 3.12-slim をベースにし、非ルートユーザー (UID 101) で動作。

## 🛠 セットアップ

### 前提条件

* Docker / Docker Compose
* (ホスト側でxattrを利用する場合) 拡張属性をサポートするファイルシステム（ext4, xfs, Btrfs等）

### ビルド

```bash
docker build -t s3proxy-deliverer .

```

## ⚙️ 環境変数

以下の環境変数で動作をカスタマイズできます。

| 変数名 | デフォルト値 | 説明 |
| --- | --- | --- |
| `STORAGE_ROOT` | `/data` | 配信するファイルのルートディレクトリ |
| `UDS_PATH` | `/var/run/s3proxy-deliverer/uvicorn.sock` | UDSモードで動作させる場合のソケットパス |
| `PORT` | `80` | TCPモードで動作させる場合のポート番号 |
| `HOST` | `0.0.0.0` | TCPモードで動作させる場合のホスト |
| `WORKERS` | `4` | Uvicornのワーカープロセス数 |

## 📖 使い方

### 1. TCPモードで起動

ポート 8080 で直接アクセスを受け付ける場合：

```bash
docker run -p 8080:80 \
  -v /path/to/your/files:/data \
  s3proxy-deliverer

```

### 2. UDSモードで起動 (Nginx連携等)

ソケットファイルを共有ボリューム経由で公開する場合：

```bash
docker run \
  -e UDS_PATH=/var/run/s3proxy-deliverer/uvicorn.sock \
  -v /tmp/sockets:/var/run/s3proxy-deliverer \
  -v /path/to/your/files:/data \
  s3proxy-deliverer

```

## 🏷 拡張属性 (xattr) の設定方法

本サーバーは配信時に以下の拡張属性を読み取ります。

| 属性名 | HTTPヘッダー | デフォルト値 |
| --- | --- | --- |
| `user.user.content-type` | `Content-Type` | `application/octet-stream` |
| `user.user.cache-control` | `Cache-Control` | `max-age=31536000, immutable` |
| `user.user.content-disposition` | `Content-Disposition` | `inline` |

**設定例 (Linux):**

```bash
# Content-Type を image/webp に設定
setfattr -n user.user.content-type -v "image/webp" /path/to/data/image.webp

# Cache-Control を設定
setfattr -n user.user.cache-control -v "public, max-age=3600" /path/to/data/image.webp

```

## 🔒 セキュリティ

* **実行ユーザー**: コンテナは UID:101 (`appuser`) で実行されます。
* **パス制限**: `STORAGE_ROOT` 以外のパスへのアクセスは `403 Forbidden` を返します。

