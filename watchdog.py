#!/usr/bin/env python3
"""Minimal keep-alive watchdog for the Index-Translate proxy.

This deliberately does NOT import the heavy proxy module (HTTP server,
urllib handlers, etc.) so it stays a tiny ~10 MB process that only polls
the port and respawns the worker when needed. The worker itself is
``proxy.py serve``.

Usage:  watchdog.py [--port 8080] [--host 127.0.0.1] [--model ...]
"""
import argparse
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def find_python():
    for cand in ("python3", "python", "py"):
        try:
            subprocess.run([cand, "--version"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=10)
            return cand
        except Exception:
            continue
    return sys.executable


def port_is_listening(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def serve_already_running():
    try:
        out = subprocess.run(["pgrep", "-f", "proxy.py serve"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return True
    except Exception:
        try:
            out = subprocess.run(["tasklist", "/FO", "CSV"],
                                 capture_output=True, text=True, timeout=5)
            for line in out.stdout.splitlines():
                if "proxy.py" in line and "serve" in line:
                    return True
        except Exception:
            pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--model", default="Index-Translate-35B-A3B")
    args = ap.parse_args()

    py = find_python()
    serve = [py, os.path.join(HERE, "proxy.py"), "serve",
             "--port", str(args.port), "--host", args.host]
    if args.model != "Index-Translate-35B-A3B":
        serve += ["--model", args.model]

    print(f"Watchdog started: ensuring http://{args.host}:{args.port} is up "
          f"(check every 10s).", flush=True)
    while True:
        if (not port_is_listening(args.host if args.host != "0.0.0.0" else "127.0.0.1",
                                  args.port)) and not serve_already_running():
            try:
                subprocess.Popen(
                    serve,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if sys.platform.startswith("win") else 0,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
            except Exception:
                pass
        time.sleep(10)


if __name__ == "__main__":
    main()
