"""小满 flower 本地图片册编辑服务。

只监听 127.0.0.1，外部设备无法进入管理接口。顾客网站仍然是纯静态网页。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
IMAGE_DIR = ROOT / "assets" / "bouquets"
HOST = "127.0.0.1"
PORT = 4173
MAX_BODY_BYTES = 28 * 1024 * 1024
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
DATA_URL_PATTERN = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,(.+)$", re.DOTALL)


def read_catalog() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("bouquets"), list):
        raise ValueError("catalog.json 格式不正确")
    return payload


def write_catalog(payload: dict) -> None:
    payload["version"] = 1
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    temp_path = CATALOG_PATH.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, CATALOG_PATH)


def safe_image_path(relative_path: str) -> Path | None:
    if not relative_path.startswith("assets/bouquets/"):
        return None
    candidate = (ROOT / relative_path).resolve()
    image_root = IMAGE_DIR.resolve()
    if candidate.parent != image_root or candidate.is_symlink():
        return None
    return candidate


def save_data_url(item_id: str, image_value: str) -> str:
    match = DATA_URL_PATTERN.match(image_value)
    if not match:
        return image_value
    mime_type, encoded = match.groups()
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime_type]
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("图片过大")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = IMAGE_DIR / f"{item_id}{extension}"
    output_path.write_bytes(raw)
    return output_path.relative_to(ROOT).as_posix()


class CatalogHandler(SimpleHTTPRequestHandler):
    server_version = "XiaomanCatalog/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        if self.path.startswith("/api/") or self.path.startswith("/catalog.json"):
            self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("请求长度不正确") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("请求内容为空或过大")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("请求格式不正确")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/api/catalog":
            try:
                self.send_json(read_catalog())
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/bouquets":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            item = self.read_json_body()
            item_id = str(item.get("id", ""))
            if not ID_PATTERN.fullmatch(item_id):
                raise ValueError("花束编号不正确")
            name = str(item.get("name", "")).strip()
            if not name:
                raise ValueError("请填写花束名字")
            item["name"] = name[:40]
            item["image"] = save_data_url(item_id, str(item.get("image", "")))
            item["sample"] = bool(item.get("sample", False))

            catalog = read_catalog()
            bouquets = catalog["bouquets"]
            existing_index = next((i for i, entry in enumerate(bouquets) if entry.get("id") == item_id), None)
            if existing_index is None:
                bouquets.append(item)
            else:
                old_image = str(bouquets[existing_index].get("image", ""))
                bouquets[existing_index] = item
                if old_image and old_image != item["image"]:
                    old_path = safe_image_path(old_image)
                    if old_path and old_path.exists() and old_path.is_file():
                        old_path.unlink()
            write_catalog(catalog)
            self.send_json(item)
        except (ValueError, json.JSONDecodeError, base64.binascii.Error) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        prefix = "/api/bouquets/"
        if not path.startswith(prefix):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            item_id = unquote(path[len(prefix):])
            if not ID_PATTERN.fullmatch(item_id):
                raise ValueError("花束编号不正确")
            catalog = read_catalog()
            target = next((entry for entry in catalog["bouquets"] if entry.get("id") == item_id), None)
            if target is None:
                self.send_json({"error": "没有找到这束花"}, HTTPStatus.NOT_FOUND)
                return
            catalog["bouquets"] = [entry for entry in catalog["bouquets"] if entry.get("id") != item_id]
            write_catalog(catalog)
            image_path = safe_image_path(str(target.get("image", "")))
            if image_path and image_path.exists() and image_path.is_file():
                image_path.unlink()
            self.send_json({"ok": True})
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[图册] {self.address_string()} - {format % args}")


def main() -> None:
    url = f"http://{HOST}:{PORT}/"
    server = ThreadingHTTPServer((HOST, PORT), CatalogHandler)
    print("小满 flower 图册编辑器已启动")
    print(f"编辑地址：{url}")
    print("完成编辑后可以关闭这个窗口。")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n编辑器已关闭。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

