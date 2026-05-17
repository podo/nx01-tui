"""NX01-tui command-line entry point — tui, chat, watch, update commands."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from nx01_tui import __version__

# Repo source for `nx01-tui update`. Override with NX01_TUI_SOURCE env var
# (lets you pin to a fork / branch).
_DEFAULT_SOURCE = os.environ.get("NX01_TUI_SOURCE", "git+https://github.com/podo/nx01-tui")


def _env_default(name: str, fallback: str | None = None) -> str | None:
    """Read an env var, treating empty string as unset."""
    val = os.environ.get(name)
    return val if val else fallback


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


def _detect_installer() -> str:
    """Return 'uv-tool' | 'uv-pip' | 'pip' based on how nx01-tui is installed."""
    # uv tool keeps an isolated env per tool — check `uv tool list`.
    if shutil.which("uv"):
        try:
            r = subprocess.run(
                ["uv", "tool", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0 and "nx01-tui" in r.stdout:
                return "uv-tool"
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Project venv with uv: prefer uv pip over plain pip if uv is available.
    if shutil.which("uv"):
        return "uv-pip"
    return "pip"


def _cmd_update(args: argparse.Namespace) -> int:
    """Reinstall nx01-tui from `--source` (default: GitHub HEAD)."""
    source = args.source or _DEFAULT_SOURCE
    method = args.method or _detect_installer()

    print(f"Updating nx01-tui from {source}  (via {method})")

    if method == "uv-tool":
        cmd = ["uv", "tool", "install", "--reinstall", source]
    elif method == "uv-pip":
        cmd = ["uv", "pip", "install", "--upgrade", "--force-reinstall", source]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--force-reinstall", source]

    print("  $", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode == 0:
        # Re-resolve nx01_tui.__version__ from the fresh install in a subprocess.
        try:
            check = subprocess.run(
                [sys.executable, "-c", "import nx01_tui; print(nx01_tui.__version__)"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            new_v = check.stdout.strip() or "?"
            print(f"  ✓ Now on nx01-tui {new_v} (was {__version__})")
        except (OSError, subprocess.TimeoutExpired):
            print("  ✓ Update completed (version check skipped).")
    return result.returncode


def _cmd_install(args: argparse.Namespace) -> int:
    """Install or reinstall nx01-tui + run the smoke test to verify."""
    print("─" * 60)
    print(" nx01-tui install — reinstall + verify")
    print("─" * 60)
    rc = _cmd_update(args)
    if rc != 0:
        return rc
    print()
    print("─" * 60)
    print(" Running built-in smoke test")
    print("─" * 60)
    return _cmd_test(args)


def _cmd_test(args: argparse.Namespace) -> int:
    """Built-in smoke test — verifies the install boots end-to-end.

    Doesn't require pytest / dev deps. Runs the Textual app under run_test()
    and asserts every layer (state, widgets, modals, client) imports and
    composes correctly. Optionally probes a real backend if --url is set.
    """
    import asyncio

    print("nx01-tui self-test")
    print(f"  version: {__version__}")

    # Step 1: import every public surface.
    try:
        from nx01_tui.tui import (  # noqa: F401
            client,
            events,
            state,
        )
        from nx01_tui.tui.app import Nx01App  # noqa: F401
        from nx01_tui.tui.modals import (  # noqa: F401
            CommandModal,
            ConfirmModal,
            DebugModal,
            HelpModal,
            MemoryModal,
            PermissionModal,
            SessionsModal,
        )
        from nx01_tui.tui.widgets import (  # noqa: F401
            AppHeader,
            ChatInput,
            CodeBlock,
            ConversationView,
            FilePickerDropdown,
            FlavorPane,
            MonitorSidebar,
            SearchBar,
            SlashDropdown,
            StatusBar,
            ThinkingBlock,
            ToolCallBlock,
        )

        print("  ✓ imports clean")
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ import failed: {exc}")
        return 1

    # Step 2: headless app boot — uses Textual's run_test().
    async def _boot_smoke() -> tuple[bool, str]:
        try:
            from nx01_tui.tui.app import Nx01App as _App  # local import after step 1

            app = _App(
                args.url or "http://localhost:65535",
                api_key=getattr(args, "api_key", None),
                flavors=["assistant", "operator"],
            )
            async with app.run_test(size=(160, 40)) as pilot:
                # Give the bootstrap worker time to complete — flavor
                # discovery can take a few seconds on slow networks.
                await pilot.pause(3.5)
                if len(app._states) < 2:
                    return False, f"only {len(app._states)} flavors mounted"
                if not isinstance(app.focused, type(app.query_one(ChatInput))):
                    return (
                        False,
                        f"ChatInput not focused on boot (focused={type(app.focused).__name__})",
                    )
                # Open + close the command modal to verify modal stack works.
                await pilot.press("ctrl+p")
                await pilot.pause(0.15)
                if app.screen.__class__.__name__ != "CommandModal":
                    return False, "ctrl+p didn't open CommandModal"
                await pilot.press("escape")
                await pilot.pause(0.1)
            return True, ""
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"

    ok, detail = asyncio.run(_boot_smoke())
    if ok:
        print("  ✓ headless boot + modal stack")
    else:
        print(f"  ✗ boot smoke failed: {detail}")
        return 1

    # Step 3: optional live-backend probe if URL + key are provided.
    if args.url and args.url != "http://localhost:8000" and args.api_key:
        rc = _cmd_doctor(args)
        if rc != 0:
            print("  ✗ backend probe failed")
            return rc
    elif args.url and args.url != "http://localhost:8000":
        print("  · skipping live probe (no --api-key)")
    else:
        print("  · skipping live probe (set NX01_URL + NX01_API_KEY to enable)")

    print("\n✓ nx01-tui is installed and working.")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Quick connectivity + auth check against the NX01 server."""
    url = (args.url or "").rstrip("/")
    if not url:
        print("error: --url required (or set NX01_URL).", file=sys.stderr)
        return 2
    key = args.api_key
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    checks = [
        ("/health", False),
        ("/flavors", True),
        ("/commands", True),
        ("/tools", False),
    ]
    print(f"NX01 doctor — {url}")
    failures = 0
    for path, auth_required in checks:
        req = urllib.request.Request(url + path, headers=headers if auth_required else {})
        label = f"  {path}{' (auth)' if auth_required else ''}"
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"{label:30}  HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            failures += 1
            hint = ""
            if e.code in (401, 403):
                hint = "  ← --api-key wrong or missing (must be 64 hex chars)"
            print(f"{label:30}  HTTP {e.code}{hint}")
        except urllib.error.URLError as e:
            failures += 1
            print(f"{label:30}  unreachable: {e.reason}")
    print(f"\n{'✓ OK' if failures == 0 else f'✗ {failures} failed'}")
    return 0 if failures == 0 else 1


def _default_url() -> str:
    return _env_default("NX01_URL", "http://localhost:8000") or "http://localhost:8000"


def _add_conn_args(
    p: argparse.ArgumentParser,
    flavor: bool = False,
    flavor_default: str | None = "assistant",
) -> None:
    """Shared --url / --api-key / --flavor with env-var defaults.

    `flavor_default` controls the fallback when neither --flavor nor
    NX01_FLAVOR is set. `watch` uses None (=all flavors); `chat` uses
    "assistant".
    """
    p.add_argument(
        "--url",
        default=_default_url(),
        help="NX01 base URL (env: NX01_URL)",
    )
    p.add_argument(
        "--api-key",
        dest="api_key",
        default=_env_default("NX01_API_KEY"),
        help="Bearer token (env: NX01_API_KEY)",
    )
    if flavor:
        p.add_argument(
            "--flavor",
            default=_env_default("NX01_FLAVOR", flavor_default),
            help="Target flavor (env: NX01_FLAVOR)",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nx01-tui",
        description="NX01 client — TUI, chat, watch, doctor, update.",
        epilog=(
            "Env vars: NX01_URL, NX01_API_KEY, NX01_FLAVOR, NX01_TUI_SOURCE.\n"
            "Run `nx01-tui doctor` to check connectivity, "
            "`nx01-tui update` to upgrade from GitHub."
        ),
    )
    parser.add_argument("--version", action="version", version=f"nx01-tui {__version__}")
    sub = parser.add_subparsers(dest="command")

    tui_p = sub.add_parser("tui", help="Launch the full-screen fleet operator TUI")
    _add_conn_args(tui_p)

    chat_p = sub.add_parser("chat", help="Single-turn chat with a flavor")
    _add_conn_args(chat_p, flavor=True)

    watch_p = sub.add_parser("watch", help="Stream live agent events from /events")
    _add_conn_args(watch_p, flavor=True, flavor_default=None)

    doctor_p = sub.add_parser("doctor", help="Probe /health + auth-gated endpoints")
    _add_conn_args(doctor_p)

    test_p = sub.add_parser("test", help="Built-in smoke test — verifies the install")
    _add_conn_args(test_p)

    for name, helptext in [
        ("install", "Install (or reinstall) nx01-tui + run smoke test"),
        ("update", "Reinstall nx01-tui from GitHub HEAD"),
    ]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument(
            "--source",
            default=None,
            help=f"pip/uv source (default: ${{NX01_TUI_SOURCE}} or {_DEFAULT_SOURCE})",
        )
        p.add_argument(
            "--method",
            choices=("uv-tool", "uv-pip", "pip"),
            default=None,
            help="Force a specific installer (default: auto-detect)",
        )
        # `install` also runs the smoke test → needs --url/--api-key.
        if name == "install":
            _add_conn_args(p)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "tui": _cmd_tui,
        "chat": _cmd_chat,
        "watch": _cmd_watch,
        "doctor": _cmd_doctor,
        "test": _cmd_test,
        "install": _cmd_install,
        "update": _cmd_update,
    }
    handler = handlers.get(args.command or "")
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
