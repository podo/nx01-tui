"""tests/test_cli.py — CLI commands (tui, chat, watch, doctor, test, install, update)."""

import io
from unittest.mock import MagicMock, patch

import pytest

from nx01_tui.cli import (
    _cmd_test,
    _cmd_tui,
    _cmd_update,
    _detect_installer,
    _render_watch_event,
    build_parser,
)

# ---------------------------------------------------------------------------
# CLI parsers
# ---------------------------------------------------------------------------


class TestCLIParser:
    def test_tui_subparser_registered(self):
        args = build_parser().parse_args(["tui", "--url", "http://localhost:8000"])
        assert args.command == "tui"
        assert args.url == "http://localhost:8000"

    def test_tui_subparser_api_key(self):
        args = build_parser().parse_args(["tui", "--api-key", "secret"])
        assert args.api_key == "secret"

    def test_tui_subparser_defaults(self):
        args = build_parser().parse_args(["tui"])
        assert args.url == "http://localhost:8000"
        assert args.api_key is None

    def test_chat_subparser_defaults(self):
        args = build_parser().parse_args(["chat"])
        assert args.url == "http://localhost:8000"
        assert args.flavor == "assistant"
        assert args.api_key is None

    def test_chat_subparser_flavor(self):
        args = build_parser().parse_args(["chat", "--flavor", "operator"])
        assert args.flavor == "operator"

    def test_watch_subparser_flavor(self):
        args = build_parser().parse_args(["watch", "--flavor", "assistant"])
        assert args.flavor == "assistant"

    def test_watch_subparser_no_flavor(self):
        args = build_parser().parse_args(["watch"])
        assert args.flavor is None


# ---------------------------------------------------------------------------
# _render_watch_event
# ---------------------------------------------------------------------------


class TestRenderWatchEvent:
    def test_chunk_event_renders_text(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _render_watch_event(
                {"type": "AgentChunkEvent", "flavor": "assistant", "text": "hello", "at": 0},
                None,
                None,
            )
        assert "hello" in buf.getvalue()

    def test_chunk_event_respects_flavor_filter(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _render_watch_event(
                {"type": "AgentChunkEvent", "flavor": "assistant", "text": "hello", "at": 0},
                "operator",
                None,
            )
        assert buf.getvalue() == ""

    def test_thinking_event_renders(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _render_watch_event(
                {"type": "AgentThinkingEvent", "flavor": "assistant", "text": "thinking", "at": 0},
                None,
                None,
            )
        assert "thinking" in buf.getvalue()

    def test_tool_event_renders(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _render_watch_event(
                {
                    "type": "ToolCallEvent",
                    "flavor": "assistant",
                    "tool": "Bash",
                    "title": "ls /",
                    "status": "done",
                    "at": 0,
                },
                None,
                None,
            )
        assert "Bash" in buf.getvalue()

    def test_turn_done_event_renders(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _render_watch_event(
                {
                    "type": "AgentTurnDoneEvent",
                    "flavor": "assistant",
                    "stop_reason": "end_turn",
                    "at": 0,
                },
                None,
                None,
            )
        assert "end_turn" in buf.getvalue()

    def test_status_event_renders(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            _render_watch_event(
                {"type": "FlavorStatusEvent", "flavor": "assistant", "status": "running", "at": 0},
                None,
                None,
            )
        assert "running" in buf.getvalue()


# ---------------------------------------------------------------------------
# _cmd_tui
# ---------------------------------------------------------------------------


class TestCmdTui:
    def test_tui_launches_app(self):
        args = build_parser().parse_args(["tui", "--url", "http://localhost:8000"])
        with patch("nx01_tui.tui.app.Nx01TuiApp") as MockApp:
            mock_instance = MagicMock()
            MockApp.return_value = mock_instance
            _cmd_tui(args)
            MockApp.assert_called_once_with(base_url="http://localhost:8000", api_key=None)
            mock_instance.run.assert_called_once()


# ---------------------------------------------------------------------------
# New commands: doctor / test / install / update + env-var defaults
# ---------------------------------------------------------------------------


class TestNewSubcommands:
    def test_doctor_subparser_registered(self):
        args = build_parser().parse_args(["doctor", "--url", "https://x"])
        assert args.command == "doctor"
        assert args.url == "https://x"

    def test_test_subparser_registered(self):
        args = build_parser().parse_args(["test"])
        assert args.command == "test"

    def test_install_subparser_registered(self):
        args = build_parser().parse_args(["install", "--source", "git+http://x"])
        assert args.command == "install"
        assert args.source == "git+http://x"

    def test_update_subparser_registered(self):
        args = build_parser().parse_args(["update", "--method", "pip"])
        assert args.command == "update"
        assert args.method == "pip"


class TestEnvVarDefaults:
    def test_tui_reads_NX01_URL(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NX01_URL", "https://prod.example.com")
        args = build_parser().parse_args(["tui"])
        assert args.url == "https://prod.example.com"

    def test_tui_reads_NX01_API_KEY(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NX01_API_KEY", "k123")
        args = build_parser().parse_args(["tui"])
        assert args.api_key == "k123"

    def test_chat_reads_NX01_FLAVOR(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NX01_FLAVOR", "operator")
        args = build_parser().parse_args(["chat"])
        assert args.flavor == "operator"

    def test_explicit_arg_wins_over_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NX01_URL", "https://env-url")
        args = build_parser().parse_args(["tui", "--url", "https://cli-url"])
        assert args.url == "https://cli-url"

    def test_empty_env_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("NX01_URL", "")
        args = build_parser().parse_args(["tui"])
        assert args.url == "http://localhost:8000"


class TestUpdateCommand:
    def test_detect_installer_returns_one_of(self):
        result = _detect_installer()
        assert result in ("uv-tool", "uv-pip", "pip")

    def test_update_calls_correct_subprocess_for_uv_tool(self, monkeypatch: pytest.MonkeyPatch):
        args = build_parser().parse_args(["update", "--method", "uv-tool"])
        seen: list[list[str]] = []

        class _Result:
            returncode = 0
            stdout = ""

        def fake_run(cmd, *a, **kw):
            seen.append(cmd)
            return _Result()

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = _cmd_update(args)
        assert rc == 0
        assert seen[0][0:3] == ["uv", "tool", "install"]
        assert "--reinstall" in seen[0]

    def test_update_uses_pip_when_forced(self, monkeypatch: pytest.MonkeyPatch):
        args = build_parser().parse_args(["update", "--method", "pip"])
        seen: list[list[str]] = []

        class _Result:
            returncode = 0
            stdout = ""

        monkeypatch.setattr(
            "subprocess.run", lambda cmd, *a, **kw: (seen.append(cmd), _Result())[1]
        )
        rc = _cmd_update(args)
        assert rc == 0
        assert seen[0][1:4] == ["-m", "pip", "install"]
        assert "--upgrade" in seen[0]


class TestSelfTest:
    def test_test_command_passes_with_no_backend(self, monkeypatch: pytest.MonkeyPatch):
        """Self-test should pass with imports + headless boot when no URL/key."""
        monkeypatch.delenv("NX01_URL", raising=False)
        monkeypatch.delenv("NX01_API_KEY", raising=False)
        args = build_parser().parse_args(["test"])
        # Override the live probe URL fallback so it skips.
        args.url = "http://localhost:8000"
        rc = _cmd_test(args)
        assert rc == 0
