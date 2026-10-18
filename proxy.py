#!/usr/bin/env python3
"""Bilibili Index-Translate local OpenAI-compatible proxy.

A thin, zero-dependency local bridge that exposes Bilibili's free public
translation API (https://index-translate.bilibili.com/v1) as a standard
OpenAI-compatible endpoint, so browser extensions such as 陪读蛙 / Immersive
Translate can use it as a "custom OpenAI translation service".

Why this exists (the gotchas it hides):
  * It ALWAYS injects ``chat_template_kwargs={"enable_thinking": False}``.
    Without it the model emits a Chain-of-Thought block instead of the
    translation, which breaks any client expecting clean text.
  * It defaults ``temperature`` to 0 (greedy decoding) for stable output.
  * No API key is required upstream; any client-supplied key is accepted.
  * Egress is adaptive: DIRECT first, then the system proxy (HTTPS_PROXY).
    This works whether or not your local proxy (Clash/v2ray) is running, and
    picks up toggles without a restart.
  * IPv4 is forced because getaddrinfo otherwise prefers an unroutable IPv6
    address on some networks.

Subcommands:
    proxy.py serve                 # run the proxy (foreground)
    proxy.py install               # register autostart (current user)
    proxy.py uninstall             # remove autostart
    proxy.py test                  # self-check both egress paths
    proxy.py watchdog              # keep-alive loop (used by install)

Stdlib only — runs on any Python 3.8+.
"""

import argparse
import http.client
import http.server
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

UPSTREAM_PROXY_OVERRIDE = os.environ.get("INDEX_TRANSLATE_UPSTREAM_PROXY", "")

DEFAULT_API_BASE = "https://index-translate.bilibili.com/v1"
DEFAULT_MODEL = "Index-Translate-35B-A3B"
DEFAULT_PORT = 8080
HEALTH_PATH = "/healthz"

AVAILABLE_MODELS = [
    "Index-Translate-35B-A3B",
    "Index-Translate-9B",
    "Index-Translate-2B",
]

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOG = os.path.join(HERE, "proxy_requests.log")


def debug_log(msg):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def detect_system_proxy():
    """Return the system egress proxy URL (or "" if none configured)."""
    if UPSTREAM_PROXY_OVERRIDE:
        return UPSTREAM_PROXY_OVERRIDE
    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(key)
        if val:
            return val
    return ""


# --------------------------------------------------------------------------
# Adaptive egress
# --------------------------------------------------------------------------
class IPv4HTTPConnection(http.client.HTTPConnection):
    def connect(self):
        addrs = socket.getaddrinfo(self.host, self.port, socket.AF_INET)
        ip = addrs[0][4][0]
        self.sock = socket.create_connection((ip, self.port), self.timeout)


class IPv4HTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addrs = socket.getaddrinfo(self.host, self.port, socket.AF_INET)
        ip = addrs[0][4][0]
        self.sock = socket.create_connection((ip, self.port), self.timeout)
        if not getattr(self, "_tunnel_host", None):
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class IPv4HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(IPv4HTTPConnection, req)


class IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(IPv4HTTPSConnection, req)


def build_openers():
    """Direct-first, then system proxy. Detected per call so toggling the
    local proxy on/off is picked up without a restart."""
    openers = [urllib.request.build_opener(IPv4HTTPHandler, IPv4HTTPSHandler)]
    proxy = detect_system_proxy()
    if proxy:
        try:
            ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            # Default handlers so the proxy CONNECT tunnel works; our custom
            # IPv4 handler would otherwise bypass the proxy.
            openers.append(urllib.request.build_opener(ph))
            debug_log(f"system/override proxy available (fallback): {proxy}")
        except Exception as e:  # noqa: BLE001
            debug_log(f"proxy handler build failed: {e!r}")
    return openers


def open_with_fallback(req, timeout, openers):
    """Return the first 2xx response. Non-2xx / connection errors fall through
    to the next path; only the last error is raised if every path fails."""
    last_err = None
    last_bad = None
    for idx, op in enumerate(openers):
        use_timeout = 10 if idx == 0 else timeout
        try:
            resp = op.open(req, timeout=use_timeout)
            if getattr(resp, "status", 0) // 100 == 2:
                return resp
            last_bad = resp
            debug_log(f"opener {idx} non-2xx {getattr(resp, 'status', '?')}; next")
        except urllib.error.HTTPError as e:
            last_bad = e
            debug_log(f"opener {idx} HTTPError {e.code}; next")
        except Exception as e:  # noqa: BLE001
            last_err = e
            debug_log(f"opener {idx} failed: {e!r}")
    if last_bad is not None:
        return last_bad
    raise last_err if last_err else OSError("no opener available")


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------
def build_cors_preflight(handler):
    handler.send_response(204)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "*")
    handler.send_header("Access-Control-Max-Age", "86400")
    handler.end_headers()


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    api_base = DEFAULT_API_BASE
    default_model = DEFAULT_MODEL

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {fmt % args}\n")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/v1/models", "/models"):
            body = json.dumps({
                "object": "list",
                "data": [{"id": m, "object": "model", "created": 0, "owned_by": "bilibili"}
                         for m in AVAILABLE_MODELS],
            }).encode("utf-8")
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path in ("/", HEALTH_PATH, "/v1" + HEALTH_PATH):
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Index-Translate Proxy Ready\n")
        else:
            self.send_response(404)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path.endswith("/chat/completions"):
            upstream_path = "/chat/completions"
        elif path.endswith("/responses"):
            upstream_path = "/responses"
        elif path.endswith("/completions"):
            upstream_path = "/completions"
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            debug_log(f"PARSE FAIL path={path} err={e!r}")
            self.send_response(400)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"bad request: {e}"}).encode("utf-8"))
            return

        if "messages" not in payload:
            if "input" in payload and isinstance(payload["input"], str):
                payload["messages"] = [{"role": "user", "content": payload["input"]}]
            elif isinstance(payload.get("input"), list):
                texts = []
                for it in payload["input"]:
                    if isinstance(it, dict):
                        texts.append(it.get("content") or it.get("text") or "")
                    else:
                        texts.append(str(it))
                payload["messages"] = [{"role": "user", "content": "\n".join(t for t in texts if t)}]
        if not payload.get("messages"):
            self.send_response(400)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "no messages/input provided"}).encode("utf-8"))
            return

        payload["model"] = payload.get("model") or self.default_model
        if not isinstance(payload.get("chat_template_kwargs"), dict):
            payload["chat_template_kwargs"] = {}
        payload["chat_template_kwargs"]["enable_thinking"] = False
        if payload.get("temperature") is None:
            payload["temperature"] = 0.0

        body = json.dumps(payload).encode("utf-8")
        upstream_url = f"{self.api_base.rstrip('/')}{upstream_path}"
        debug_log(f"IN path={path} model={payload.get('model')} "
                  f"msgs={json.dumps(payload.get('messages'), ensure_ascii=False)[:300]}")
        req = urllib.request.Request(
            upstream_url, data=body,
            headers={"Content-Type": "application/json", "User-Agent": "Index-Translate-Proxy/1.0"},
            method="POST",
        )

        response_started = False
        try:
            resp = open_with_fallback(req, 120, build_openers())
            with resp:
                response_started = True
                self.close_connection = True
                self.send_response(resp.code)
                self._cors()
                for k, v in resp.headers.items():
                    if k.lower() in ("content-type", "cache-control", "content-encoding", "retry-after"):
                        self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = resp.read1(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except Exception as e:  # noqa: BLE001
            debug_log(f"UPSTREAM FAIL url={upstream_url!r} err={e!r}")
            self.close_connection = True
            if response_started:
                return
            try:
                self.send_response(502)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            except OSError:
                self.close_connection = True


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def find_python():
    """Best-effort cross-platform python interpreter for spawning children."""
    for cand in ("python3", "python", "py"):
        try:
            subprocess.run([cand, "--version"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            return cand
        except Exception:
            continue
    return sys.executable


def run_serve(args):
    ProxyHandler.api_base = args.api_base
    ProxyHandler.default_model = args.model
    if args.upstream_proxy:
        global UPSTREAM_PROXY_OVERRIDE
        UPSTREAM_PROXY_OVERRIDE = args.upstream_proxy
    if args.model not in AVAILABLE_MODELS:
        sys.stderr.write(
            f"Warning: --model '{args.model}' is unknown. "
            f"Known: {', '.join(AVAILABLE_MODELS)}. Continuing.\n")
    server = http.server.ThreadingHTTPServer((args.host, args.port), ProxyHandler)
    display_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print("=" * 64)
    print(" Index-Translate Local Proxy (OpenAI-compatible) is running")
    print("=" * 64)
    print(f" Local endpoint : http://{display_host}:{args.port}/v1")
    print(f" Upstream API   : {args.api_base}")
    print(f" Default model  : {args.model}")
    print(" 陪读蛙 / Immersive Translate configuration:")
    print(f"   API URL : http://{display_host}:{args.port}/v1")
    print(f"   Model   : {args.model}")
    print("   API Key : (any string, e.g. index)")
    print("=" * 64, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down proxy...")
    finally:
        server.server_close()


def port_is_listening(host, port, timeout=2):
    import socket as _s
    try:
        with _s.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def run_test(args):
    """Self-check: probe both egress paths and report, reusing the same
    fallback logic the server uses (so the result matches real behavior)."""
    print(f"Testing upstream reachability for {args.api_base} ...")
    test_payload = {
        "model": args.model,
        "messages": [{"role": "user",
                      "content": "请将以下文本翻译为英语：你好，世界。"}],
        "temperature": 0, "max_tokens": 64,
    }
    req = urllib.request.Request(
        f"{args.api_base.rstrip('/')}/chat/completions",
        data=json.dumps(test_payload).encode(),
        headers={"Content-Type": "application/json",
                 "User-Agent": "Index-Translate-Proxy/1.0"},
        method="POST")
    ok = False
    try:
        resp = open_with_fallback(req, 60, build_openers())
        txt = resp.read().decode()
        try:
            out = json.loads(txt)["choices"][0]["message"]["content"]
        except Exception:
            out = txt[:80]
        print(f"  OK -> {out}")
        ok = True
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED: {e!r}")
    print("RESULT:", "PASS" if ok else "FAIL — cannot reach upstream on any path")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# Autostart (cross-platform, current user)
# --------------------------------------------------------------------------
def _autostart_windows(vbs_path):
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                         winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, "IndexTranslateProxy", 0, winreg.REG_SZ,
                      f'wscript.exe "{vbs_path}"')
    key.Close()


def _autostart_systemd(unit_path, unit_name):
    unit = f"""[Unit]
Description=Index-Translate Local Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={find_python()} "{os.path.join(HERE, 'proxy.py')}" serve
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""
    os.makedirs(os.path.dirname(unit_path), exist_ok=True)
    with open(unit_path, "w", encoding="utf-8") as f:
        f.write(unit)
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "--now", unit_name], check=False)
    except Exception as e:  # noqa: BLE001
        print(f"(systemctl enable skipped: {e})")


def install_autostart(args):
    system = sys.platform
    if system.startswith("win"):
        vbs = os.path.join(HERE, "start_hidden.vbs")
        _autostart_windows(vbs)
        print(f"Registered Windows autostart (Run key) -> {vbs}")
        print("Launching now...")
        subprocess.run(["wscript.exe", vbs], check=False)
    elif system.startswith("linux"):
        unit_name = "index-translate-proxy.service"
        unit_path = os.path.expanduser(f"~/.config/systemd/user/{unit_name}")
        _autostart_systemd(unit_path, unit_name)
        print(f"Registered systemd user service: {unit_path}")
    elif system == "darwin":
        print("macOS: please run 'proxy.py serve' via a launchd plist (see README).")
    else:
        print(f"Autostart not automated for platform {system}; run 'proxy.py serve' manually.")
    return 0


def uninstall_autostart(args):
    system = sys.platform
    if system.startswith("win"):
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "IndexTranslateProxy")
            key.Close()
            print("Removed Windows autostart entry.")
        except FileNotFoundError:
            print("No Windows autostart entry found.")
    elif system.startswith("linux"):
        unit_name = "index-translate-proxy.service"
        subprocess.run(["systemctl", "--user", "disable", "--now", unit_name], check=False)
        print("Disabled systemd user service.")
    return 0


def run_watchdog(args):
    """Keep-alive: if the port is not listening, spawn 'serve'. Loops forever."""
    py = find_python()
    serve = [py, os.path.join(HERE, "proxy.py"), "serve",
             "--port", str(args.port), "--host", args.host]
    if args.model != DEFAULT_MODEL:
        serve += ["--model", args.model]
    print(f"Watchdog started: ensuring http://{args.host}:{args.port} is up "
          f"(check every 30s).", flush=True)
    while True:
        if not port_is_listening(args.host if args.host != "0.0.0.0" else "127.0.0.1",
                                 args.port):
            debug_log("watchdog: port down, starting serve")
            try:
                # DEVNULL avoids file-lock contention on shared log files.
                subprocess.Popen(
                    serve,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if sys.platform.startswith("win") else 0,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
            except Exception as e:  # noqa: BLE001
                debug_log(f"watchdog spawn failed: {e!r}")
        time.sleep(10)


def run_setup(args):
    """Interactive, foolproof setup wizard:
    check Python -> start proxy -> self-test -> ask autostart -> print config."""
    print("=" * 60)
    print(" Index-Translate Local Proxy — Setup")
    print("=" * 60)

    # 1) Python sanity
    py = find_python()
    if py == sys.executable and not _python_runs(py):
        print("\n[ERROR] Python 3.8+ not found.")
        print("Download & install from https://www.python.org/downloads/")
        print("  (Windows: tick 'Add python.exe to PATH' during install)\n")
        input("Press Enter to exit...")
        return 2
    print(f"[OK] Python runtime: {py}")

    # 2) Launch the proxy via watchdog (keeps it alive, restarts on crash)
    print("[1/3] Starting proxy (with keep-alive watchdog)...")
    install_autostart_launch_only(args)

    # 3) Wait for it to come up, then self-test
    print("[2/3] Running connectivity self-check...")
    up = False
    for _ in range(20):
        if port_is_listening("127.0.0.1" if args.host == "0.0.0.0" else args.host, args.port):
            up = True
            break
        time.sleep(0.5)
    if not up:
        print("  ! Proxy did not start. Check proxy.err.log.")
        input("Press Enter to exit...")
        return 1
    rc = run_test(args)
    if rc != 0:
        print("  ! Upstream unreachable. The proxy is still running; fix network")
        print("    (e.g. turn your system proxy on/off) and retry 'proxy.py test'.")
    else:
        print("  [OK] Translation works end-to-end.")

    # 4) Ask about autostart
    print("[3/3] Autostart on login? (so it is always available)")
    try:
        ans = input("       Enable silent autostart? [Y/n]: ").strip().lower()
    except EOFError:
        ans = "y"
    if ans in ("", "y", "yes"):
        install_autostart(args)
        print("  [OK] Autostart enabled (no window on login).")
    else:
        print("  Skipped. Run 'proxy.py install' later to enable it.")

    # 5) Print the config the user pastes into 陪读蛙 / Immersive Translate
    host_disp = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print()
    print("=" * 60)
    print(" ALL DONE. Use these in your translation plugin:")
    print("=" * 60)
    print(f"   API URL  : http://{host_disp}:{args.port}/v1")
    print(f"   Model    : {args.model}")
    print(f"   API Key  : index   (any string works)")
    print("=" * 60)
    print(" Keep this window open or close it — the proxy runs in the")
    print(" background. To stop: run stop_proxy.bat (or 'proxy.py uninstall').")
    print()
    try:
        input("Press Enter to finish...")
    except EOFError:
        pass
    return 0


def _python_runs(py):
    try:
        subprocess.run([py, "--version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=10)
        return True
    except Exception:
        return False


def install_autostart_launch_only(args):
    """Launch the watchdog now (without necessarily registering autostart)."""
    system = sys.platform
    if system.startswith("win"):
        vbs = os.path.join(HERE, "start_hidden.vbs")
        # Prefer wscript (hidden); fall back to pythonw directly if wscript
        # is unavailable (locked-down environments).
        try:
            r = subprocess.run(["wscript.exe", vbs], check=False)
            if r.returncode != 0:
                raise OSError("wscript returned non-zero")
        except Exception:
            pyw = find_python().replace("py", "pythonw").replace("python", "pythonw")
            if not os.path.exists(pyw):
                pyw = "pythonw"
            subprocess.Popen(
                [pyw, os.path.join(HERE, "proxy.py"), "watchdog",
                 "--port", str(args.port), "--host", args.host],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    else:
        # Launch watchdog in background; on Linux/macOS just spawn it.
        subprocess.Popen(
            [find_python(), os.path.join(HERE, "proxy.py"), "watchdog",
             "--port", str(args.port), "--host", args.host],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, start_new_session=True,
        )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(
        description="Bilibili Index-Translate local OpenAI-compatible proxy")
    sub = ap.add_subparsers(dest="cmd")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--port", "-p", type=int, default=DEFAULT_PORT)
    common.add_argument("--host", default="127.0.0.1")
    common.add_argument("--model", "-m", default=DEFAULT_MODEL)
    common.add_argument("--api-base", default=DEFAULT_API_BASE)
    common.add_argument("--upstream-proxy", default="",
                        help="Force egress proxy (e.g. http://127.0.0.1:7890). "
                             "Empty = auto-detect from env, direct-first.")

    sub.add_parser("serve", parents=[common], help="run the proxy (foreground)")
    sub.add_parser("install", parents=[common],
                   help="register autostart for current user (runs watchdog)")
    sub.add_parser("uninstall", help="remove autostart")
    sub.add_parser("test", parents=[common], help="self-check egress paths")
    sub.add_parser("watchdog", parents=[common], help="keep-alive loop (internal)")
    sub.add_parser("setup", parents=[common],
                   help="interactive wizard: start proxy, self-test, ask autostart, print config")
    return ap


def main():
    ap = build_parser()
    args = ap.parse_args()
    cmd = args.cmd or "serve"

    if cmd == "serve":
        run_serve(args)
    elif cmd == "test":
        sys.exit(run_test(args))
    elif cmd == "install":
        # install registers the watchdog (which keeps serve alive) as autostart
        install_autostart(args)
    elif cmd == "uninstall":
        sys.exit(uninstall_autostart(args))
    elif cmd == "watchdog":
        run_watchdog(args)
    elif cmd == "setup":
        sys.exit(run_setup(args))


if __name__ == "__main__":
    main()
