"""将电脑上的小满 flower 图册一键发布到 GitHub Pages。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REMOTE_URL = "https://github.com/qi-zhang777/xiaoman-flower-catalog.git"
PUBLIC_URL = "https://qi-zhang777.github.io/xiaoman-flower-catalog/"
PUBLISH_PARENT = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "XiaomanFlowerPublisher"
PUBLISH_REPO = PUBLISH_PARENT / "repo"
SYNC_FILES = (
    ".gitignore",
    ".nojekyll",
    "README.md",
    "index.html",
    "styles.css",
    "app.js",
    "catalog.json",
    "catalog_manager.py",
    "编辑图册.cmd",
    "publish_catalog.py",
    "发布图册.cmd",
)


def run(
    command: list[str],
    cwd: Path | None = None,
    capture: bool = False,
    check: bool = True,
) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def git(*args: str, capture: bool = False, check: bool = True) -> str:
    return run(["git", *args], cwd=PUBLISH_REPO, capture=capture, check=check)


def ensure_clone() -> None:
    if (PUBLISH_REPO / ".git").is_dir():
        actual_remote = git("remote", "get-url", "origin", capture=True)
        if actual_remote.rstrip("/") != REMOTE_URL.rstrip("/"):
            raise RuntimeError("发布缓存连接到了其他仓库，请联系 Codex 处理。")
        return
    if PUBLISH_REPO.exists() and any(PUBLISH_REPO.iterdir()):
        raise RuntimeError(f"发布缓存目录不是空的：{PUBLISH_REPO}")
    PUBLISH_PARENT.mkdir(parents=True, exist_ok=True)
    print("首次发布：正在准备 GitHub 文件……")
    run(["git", "clone", "--branch", "main", "--single-branch", REMOTE_URL, str(PUBLISH_REPO)])


def ensure_clean_and_current() -> None:
    status = git("status", "--porcelain", "-z", capture=True)
    if status:
        allowed = set(SYNC_FILES)
        changed_paths = [entry[3:] for entry in status.split("\0") if entry]
        unexpected = [
            path
            for path in changed_paths
            if path not in allowed and not path.startswith("assets/bouquets/")
        ]
        if unexpected:
            raise RuntimeError("发布缓存出现了意外文件，请联系 Codex 处理。")
        print("检测到上一次未完成的安全发布，正在继续……")
        return
    git("pull", "--ff-only", "origin", "main")


def copy_site_files() -> None:
    for relative in SYNC_FILES:
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"缺少发布文件：{relative}")
        destination = PUBLISH_REPO / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    source_images = ROOT / "assets" / "bouquets"
    target_images = PUBLISH_REPO / "assets" / "bouquets"
    target_images.mkdir(parents=True, exist_ok=True)
    source_names = {
        item.name
        for item in source_images.iterdir()
        if item.is_file() and not item.is_symlink()
    }
    for item in target_images.iterdir():
        if item.is_file() and not item.is_symlink() and item.name not in source_names:
            item.unlink()
    for item in source_images.iterdir():
        if item.is_file() and not item.is_symlink():
            shutil.copy2(item, target_images / item.name)


def commit_and_push() -> bool:
    git("add", "--", *SYNC_FILES, "assets/bouquets")
    if not git("status", "--porcelain", capture=True):
        print("图册已经是最新版本，不需要重复发布。")
        return False

    if not git("config", "user.name", capture=True, check=False):
        git("config", "user.name", "小满 flower")
    if not git("config", "user.email", capture=True, check=False):
        git("config", "user.email", "xiaoman-flower-catalog@users.noreply.github.com")

    message = "Update flower catalog " + datetime.now().strftime("%Y-%m-%d %H:%M")
    git("commit", "-m", message)
    print("正在连接 GitHub……第一次使用时请在弹出的页面中确认登录。")
    git("push", "origin", "main")
    return True


def wait_for_public_update(timeout_seconds: int = 150) -> bool:
    with (ROOT / "catalog.json").open("r", encoding="utf-8") as handle:
        expected_updated_at = json.load(handle).get("updatedAt")
    print("正在等待公网网站刷新，请不要关闭这个窗口……")
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        url = PUBLIC_URL + f"catalog.json?v={int(time.time() * 1000)}"
        try:
            request = urllib.request.Request(
                url,
                headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                public_catalog = json.loads(response.read().decode("utf-8"))
            if public_catalog.get("updatedAt") == expected_updated_at:
                print("公网网站已确认更新完成。")
                return True
        except Exception:  # noqa: BLE001
            pass
        if attempts % 4 == 0:
            print("仍在等待 GitHub Pages 构建……")
        time.sleep(5)
    print("公网构建时间较长，稍后刷新页面即可看到新版。")
    return False


def main() -> int:
    try:
        print("=== 小满 flower 一键发布 ===")
        ensure_clone()
        ensure_clean_and_current()
        copy_site_files()
        changed = commit_and_push()
        if changed:
            print("\n文件推送成功！")
            print(PUBLIC_URL)
            wait_for_public_update()
        webbrowser.open(PUBLIC_URL + f"?v={int(time.time())}")
        return 0
    except FileNotFoundError:
        print("\n发布失败：没有找到 Git，请联系 Codex。")
    except subprocess.CalledProcessError as error:
        print(f"\n发布失败：Git 命令返回错误（{error.returncode}）。")
        print("请保留这个窗口，并把画面发给 Codex。")
    except Exception as error:  # noqa: BLE001
        print(f"\n发布失败：{error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
