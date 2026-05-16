"""tests/test_cli.py — Phase 6: CLI commands (chat, watch, tui)."""

import io
from unittest.mock import MagicMock, patch

from nx01_tui.cli import _cmd_tui, _render_watch_event, build_parser

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
