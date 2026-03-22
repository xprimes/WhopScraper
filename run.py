#!/usr/bin/env python
"""
一键启动：Web 看板 + 信号抓取主程序

用法:
    python run.py            # 同时启动 Web 看板 (port 5000) 和主程序
    python run.py --web      # 仅启动 Web 看板
    python run.py --main     # 仅启动主程序
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import signal
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def start_process(args: list[str], label: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        args,
        cwd=str(ROOT),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    print(f"[run] ✅ {label} 已启动 (pid={proc.pid})")
    return proc


def main():
    parser = argparse.ArgumentParser(description="WhopScraper 一键启动")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--web",  action="store_true", help="仅启动 Web 看板")
    group.add_argument("--main", action="store_true", help="仅启动主程序")
    args = parser.parse_args()

    procs: list[subprocess.Popen] = []

    run_web  = args.web  or (not args.web and not args.main)
    run_main = args.main or (not args.web and not args.main)

    if run_web:
        procs.append(start_process([PYTHON, "web/app.py"], "Web 看板  → http://localhost:5000"))
        time.sleep(0.5)   # 稍等让 Flask 先绑定端口

    if run_main:
        procs.append(start_process([PYTHON, "main.py"], "信号抓取主程序"))

    if not procs:
        return

    def shutdown(signum=None, frame=None):
        print("\n[run] 正在停止所有进程...")
        for p in procs:
            if p.poll() is None:
                p.terminate()
        # 等待最多 5 秒
        deadline = time.time() + 5
        for p in procs:
            remaining = max(0, deadline - time.time())
            try:
                p.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                p.kill()
        print("[run] 已全部停止。")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 任一进程退出就终止全部
    while True:
        for p in procs:
            if p.poll() is not None:
                print(f"[run] ⚠️  某进程 (pid={p.pid}) 已退出，正在停止其他进程...")
                shutdown()
        time.sleep(1)


if __name__ == "__main__":
    main()
