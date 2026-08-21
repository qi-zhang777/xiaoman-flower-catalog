"""将电脑上的小满 flower 图册一键发布到腾讯云，并同步 GitHub 备份。"""

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
GITHUB_PUBLIC_URL = "https://qi-zhang777.github.io/xiaoman-flower-catalog/"
CLOUDBASE_ENV_ID = "xiaoman-flower-catalog-d97e9ead0"
CLOUDBASE_PUBLIC_URL = (
    "https://xiaoman-flower-catalog-d97e9ead0-1472395158.tcloudbaseapp.com/"
)
PUBLISH_PARENT = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "XiaomanFlowerPublisher"
PUBLISH_REPO = PUBLISH_PARENT / "repo"
CLOUDBASE_DEPLOY_DIR = PUBLISH_PARENT / "cloudbase-site"
WEB_FILES = (
    "index.html",
    "styles.css",
    "app.js",
    "catalog.json",
    "assets/xiaoman-peony-cover.png",
)
SYNC_FILES = (
    ".gitignore",
    ".nojekyll",
    "README.md",
    "index.html",
    "styles.css",
    "app.js",
    "catalog.json",
    "assets/xiaoman-peony-cover.png",
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
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
        env=env,
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


def prepare_cloudbase_site() -> None:
    CLOUDBASE_DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    for relative in WEB_FILES:
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"缺少腾讯云发布文件：{relative}")
        destination = CLOUDBASE_DEPLOY_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    source_images = ROOT / "assets" / "bouquets"
    target_images = CLOUDBASE_DEPLOY_DIR / "assets" / "bouquets"
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


def cloudbase_cli_command() -> tuple[list[str], dict[str, str]]:
    bundled_root = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
    )
    pnpm_candidates = (
        Path(shutil.which("pnpm.cmd") or shutil.which("pnpm") or ""),
        bundled_root / "bin" / "fallback" / "pnpm.cmd",
    )
    pnpm = next((item for item in pnpm_candidates if item.is_file()), None)
    if pnpm is None:
        raise RuntimeError("没有找到腾讯云发布工具，请联系 Codex 处理。")

    command_env = os.environ.copy()
    bundled_node_dir = bundled_root / "node" / "bin"
    if (bundled_node_dir / "node.exe").is_file():
        command_env["PATH"] = str(bundled_node_dir) + os.pathsep + command_env.get(
            "PATH", ""
        )
    command = [
        str(pnpm),
        "--package=@cloudbase/cli",
        "dlx",
        "tcb",
        "hosting",
        "deploy",
        str(CLOUDBASE_DEPLOY_DIR),
        "-e",
        CLOUDBASE_ENV_ID,
        "--concurrency",
        "5",
        "--retry-count",
        "5",
    ]
    return command, command_env


def deploy_to_cloudbase() -> None:
    prepare_cloudbase_site()
    command, command_env = cloudbase_cli_command()
    print("正在发布到腾讯云主站……")
    run(command, cwd=ROOT, env=command_env)


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


def wait_for_public_update(
    public_url: str,
    site_name: str,
    timeout_seconds: int = 150,
) -> bool:
    with (ROOT / "catalog.json").open("r", encoding="utf-8") as handle:
        expected_updated_at = json.load(handle).get("updatedAt")
    print(f"正在等待{site_name}刷新，请不要关闭这个窗口……")
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        url = public_url + f"catalog.json?v={int(time.time() * 1000)}"
        try:
            request = urllib.request.Request(
                url,
                headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                public_catalog = json.loads(response.read().decode("utf-8"))
            if public_catalog.get("updatedAt") == expected_updated_at:
                print(f"{site_name}已确认更新完成。")
                return True
        except Exception:  # noqa: BLE001
            pass
        if attempts % 4 == 0:
            print(f"仍在等待{site_name}更新……")
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
            print("\nGitHub 备份推送成功！")
            print(GITHUB_PUBLIC_URL)

        deploy_to_cloudbase()
        print("\n腾讯云主站发布成功！")
        print(CLOUDBASE_PUBLIC_URL)
        wait_for_public_update(CLOUDBASE_PUBLIC_URL, "腾讯云主站", 90)
        webbrowser.open(CLOUDBASE_PUBLIC_URL + f"?v={int(time.time())}")

        if changed:
            wait_for_public_update(GITHUB_PUBLIC_URL, "GitHub 备份", 150)
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
