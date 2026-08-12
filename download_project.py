"""
Standalone script to download a CodeSentinel project's files from its
E2B sandbox onto your local machine. Runs directly on the host - no
Docker required - since it only needs the E2B SDK and your API key.

Setup (one-time):
    pip install e2b python-dotenv

Usage:
    python download_project.py <project-name> [output-dir]

Example:
    python download_project.py planner-v2
    python download_project.py planner-v2 ./my-blog-app
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from e2b import Sandbox

load_dotenv()

SANDBOX_MAP_FILE = Path("data/e2b_sandbox_map.json")
PROJECT_DIR = "/home/user/project"


def load_sandbox_id(project: str) -> str | None:
    if not SANDBOX_MAP_FILE.exists():
        print(f"Could not find {SANDBOX_MAP_FILE} - has any project been run yet?")
        return None
    mapping = json.loads(SANDBOX_MAP_FILE.read_text())
    return mapping.get(project)


def download(project: str, output_dir: str = None):
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("E2B_API_KEY not found. Make sure you have a .env file with it set, in this directory.")
        return

    sandbox_id = load_sandbox_id(project)
    if not sandbox_id:
        print(f"No sandbox found for project '{project}'. Known projects:")
        if SANDBOX_MAP_FILE.exists():
            mapping = json.loads(SANDBOX_MAP_FILE.read_text())
            for name in mapping:
                print(f"  - {name}")
        return

    print(f"Connecting to sandbox {sandbox_id} for project '{project}'...")
    try:
        sandbox = Sandbox.connect(sandbox_id, timeout=120)
    except Exception as e:
        print(f"Could not connect - the sandbox may have expired or been killed: {e}")
        return

    result = sandbox.commands.run(f"find {PROJECT_DIR} -type f")
    files = [
        line.replace(PROJECT_DIR + "/", "")
        for line in (result.stdout or "").strip().splitlines() if line.strip()
    ]

    if not files:
        print("No files found in this project's sandbox.")
        return

    target_root = Path(output_dir or "project")
    target_root.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(files)} file(s) to {target_root}/ ...")
    for file_path in files:
        try:
            content = sandbox.files.read(f"{PROJECT_DIR}/{file_path}")
        except Exception as e:
            print(f"  ⚠ could not read {file_path}: {e}")
            continue

        dest = target_root / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"  ✓ {file_path}")

    print(f"\nDone. Files are in: {target_root.resolve()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_project.py <project-name> [output-dir]")
        sys.exit(1)

    project_name = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None
    download(project_name, out_dir)