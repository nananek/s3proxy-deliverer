import os
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

import main


@pytest.fixture
def storage_root(tmp_path):
    with patch.object(main, "STORAGE_ROOT", tmp_path):
        yield tmp_path


@pytest.fixture
def client(storage_root):
    return TestClient(main.app)


def make_file(root: Path, name: str, content: bytes = b"hello") -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


# --- 404 ---

class TestNotFound:
    def test_missing_file(self, client):
        assert client.get("/nonexistent.txt").status_code == 404

    def test_directory_returns_404(self, client, storage_root):
        (storage_root / "subdir").mkdir()
        assert client.get("/subdir").status_code == 404


# --- セキュリティ ---

class TestSecurity:
    def test_symlink_traversal(self, client, storage_root, tmp_path):
        """storage_root 外への symlink が 403 を返す"""
        secret = tmp_path.parent / "secret.txt"
        secret.write_bytes(b"secret content")

        (storage_root / "evil.txt").symlink_to(secret)

        resp = client.get("/evil.txt")
        assert resp.status_code == 403

    def test_path_traversal_url(self, client):
        """/../ を含む URL は 403 または 404 を返す"""
        resp = client.get("/../etc/passwd")
        assert resp.status_code in (403, 404)


# --- 正常系 ---

class TestServeFile:
    def test_serve_with_all_xattrs(self, client, storage_root):
        make_file(storage_root, "test.txt", b"hello world")
        xattrs = {
            "user.user.content-type": b"text/plain",
            "user.user.cache-control": b"max-age=3600",
            "user.user.content-disposition": b"attachment; filename=test.txt",
        }

        with patch("os.getxattr", side_effect=lambda p, k: xattrs[k]):
            resp = client.get("/test.txt")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        assert resp.headers["cache-control"] == "max-age=3600"
        assert resp.headers["content-disposition"] == "attachment; filename=test.txt"
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.content == b"hello world"

    def test_serve_no_xattr_fallback(self, client, storage_root):
        """xattr なし → application/octet-stream + no-cache"""
        make_file(storage_root, "binary.bin", b"\x00\x01\x02")

        with patch("os.getxattr", side_effect=OSError()):
            resp = client.get("/binary.bin")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert resp.headers["cache-control"] == "no-cache"

    def test_serve_partial_xattr_defaults(self, client, storage_root):
        """content-type あり、cache-control/content-disposition なし → デフォルト値"""
        make_file(storage_root, "image.png", b"fakepng")

        def mock_getxattr(path, attr):
            if attr == "user.user.content-type":
                return b"image/png"
            raise OSError()

        with patch("os.getxattr", side_effect=mock_getxattr):
            resp = client.get("/image.png")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/png")
        assert resp.headers["cache-control"] == "max-age=31536000, immutable"
        assert resp.headers["content-disposition"] == "inline"

    def test_serve_file_in_subdir(self, client, storage_root):
        make_file(storage_root, "sub/dir/file.txt", b"nested content")

        with patch("os.getxattr", side_effect=OSError()):
            resp = client.get("/sub/dir/file.txt")

        assert resp.status_code == 200
        assert resp.content == b"nested content"
