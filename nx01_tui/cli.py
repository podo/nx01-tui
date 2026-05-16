"""NX01-tui command-line entry point — tui, chat, and watch commands."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from nx01_tui import __version__


def _render_watch_event(payload: dict, flavor_filter: str | None, console: object) -> None:
    """Render a single SSE event payload to the terminal."""
    from datetime import datetime

    event_type = payload.get("type", "")
    flavor = payload.get("flavor", "?")

    if flavor_filter and flavor != flavor_filter:
        return

    ts = datetime.fromtimestamp(payload.get("at", 0)).strftime("%H:%M:%S")
    prefix = f"[{ts} {flavor}]"

    if event_type == "AgentChunkEvent":
        text = payload.get("text", "")
        if console is not None:
            from rich.text import Text

            t = Text()
            t.append(prefix + " ", style="dim cyan")
            t.append(text, style="green")
            console.print(t, end="")
        else:
            print(text, end="", flush=True)

    elif event_type == "AgentThinkingEvent":
        text = payload.get("text", "")
        if console is not None:
            from rich.text import Text

            t = Text()
            t.append(f"{prefix} [thinking] ", style="dim yellow")
            t.append(text, style="dim italic")
            console.print(t, end="")
        else:
            print(f"{prefix} [thinking] {text}", end="", flush=True)

    elif event_type == "ToolCallEvent":
        tool = payload.get("tool", "?")
        title = payload.get("title") or ""
        status = payload.get("status", "")
        label = f"{tool}" + (f" — {title}" if title else "") + f" ({status})"
        if console is not None:
            from rich.text import Text

            t = Text()
            t.append(f"{prefix} ", style="dim cyan")
            t.append("⚙ " + label, style="bold blue")
            console.print(t)
        else:
            print(f"{prefix} tool: {label}")

    elif event_type == "AgentTurnDoneEvent":
        stop_reason = payload.get("stop_reason", "")
        if console is not None:
            console.print(f"\n{prefix} ✓ turn done ({stop_reason})", style="dim")
        else:
            print(f"\n{prefix} [done] {stop_reason}")

    elif event_type == "FlavorStatusEvent":
        status = payload.get("status", "")
        if console is not None:
            console.print(f"{prefix} status → {status}", style="bold")
        else:
            print(f"{prefix} status: {status}")


def _cmd_chat(args: argparse.Namespace) -> int:
    base = args.url.rstrip("/")
    flavor = args.flavor
    headers = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"
    headers["Content-Type"] = "application/json"

    print(f"Chatting with {flavor} at {base}. Ctrl+C to quit.")
    while True:
        try:
            text = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not text:
            continue
        payload = json.dumps({"target_flavor": flavor, "message": text}).encode()
        req = urllib.request.Request(
            f"{base}/message", data=payload, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError as exc:
            print(f"error: {exc}", file=sys.stderr)
            continue
        cid = data["correlation_id"]
        poll_url = f"{base}/messages/{urllib.parse.quote(cid)}"
        for _ in range(60):
            time.sleep(1)
            preq = urllib.request.Request(
                poll_url,
                headers={k: v for k, v in headers.items() if k != "Content-Type"},
            )
            try:
                with urllib.request.urlopen(preq, timeout=10) as presp:
                    pdata = json.loads(presp.read())
            except urllib.error.URLError as exc:
                print(f"poll error: {exc}", file=sys.stderr)
                break
            if pdata.get("status") == "complete":
                print(pdata.get("response", ""))
                break
        else:
            print("(timed out waiting for response)", file=sys.stderr)
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    base = args.url.rstrip("/")
    flavor_filter = args.flavor
    headers: dict[str, str] = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    try:
        from rich.console import Console

        console: object = Console()
    except ImportError:
        console = None

    url = f"{base}/events"
    req = urllib.request.Request(url, headers=headers)

    flavor_label = f" [{flavor_filter}]" if flavor_filter else " [all flavors]"
    msg = f"Watching NX01 event stream at {base}{flavor_label}. Ctrl+C to quit."
    if console is not None:
        from rich.console import Console as _Console

        if isinstance(console, _Console):
            console.print(msg, style="bold")
    else:
        print(msg)

    data_lines: list[str] = []

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            while True:
                raw = resp.readline()
                if not raw:
                    break
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    data_lines.append(line[5:].strip())
                elif line == "" or line == "\r":
                    if data_lines:
                        data_str = "\n".join(data_lines)
                        try:
                            payload = json.loads(data_str)
                        except json.JSONDecodeError:
                            pass
                        else:
                            _render_watch_event(payload, flavor_filter, console)
                    data_lines = []
    except KeyboardInterrupt:
        print()
    except urllib.error.URLError as exc:
        print(f"connection error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_tui(args: argparse.Namespace) -> int:
    from nx01_tui.tui.app import Nx01TuiApp

    app = Nx01TuiApp(base_url=args.url, api_key=args.api_key)
    app.run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nx01-tui",
        description="NX01 client — TUI, chat, and watch for the NX01 fleet",
    )
    parser.add_argument("--version", action="version", version=f"nx01-tui {__version__}")
    sub = parser.add_subparsers(dest="command")

    tui_p = sub.add_parser("tui", help="Launch the full-screen fleet operator TUI")
    tui_p.add_argument("--url", default="http://localhost:8000", help="NX01 base URL")
    tui_p.add_argument("--api-key", dest="api_key", default=None, help="NX01_API_KEY bearer token")

    chat_p = sub.add_parser("chat", help="Interactive chat with a flavor via the NX01 API")
    chat_p.add_argument("--url", default="http://localhost:8000", help="NX01 base URL")
    chat_p.add_argument("--flavor", default="assistant", help="Target flavor name")
    chat_p.add_argument("--api-key", dest="api_key", default=None, help="NX01_API_KEY bearer token")

    watch_p = sub.add_parser("watch", help="Stream live agent events from the NX01 event bus")
    watch_p.add_argument("--url", default="http://localhost:8000", help="NX01 base URL")
    watch_p.add_argument(
        "--flavor", default=None, help="Filter to a specific flavor (default: all)"
    )
    watch_p.add_argument(
        "--api-key", dest="api_key", default=None, help="NX01_API_KEY bearer token"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "chat":
        return _cmd_chat(args)
    if args.command == "watch":
        return _cmd_watch(args)
    if args.command == "tui":
        return _cmd_tui(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
