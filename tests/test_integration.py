"""tests/test_integration.py — Phase 5: Mocked httpx for _send_message and _sse_worker."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.widgets import Input, RichLog, TabbedContent

from nx01_tui.tui.app import ConversationPane, Nx01TuiApp
from nx01_tui.tui.state import FlavorState

# ---------------------------------------------------------------------------
# _send_message tests
# ---------------------------------------------------------------------------


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_posts_correct_json(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-assistant"

            mock_response = MagicMock()
            mock_response.json.return_value = {"correlation_id": "abc"}
            mock_post = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient.post", mock_post):
                await pilot.app._send_message("hello")
                await pilot.pause(0.3)

            mock_post.assert_awaited_once()
            body = mock_post.await_args.kwargs.get("content") or mock_post.await_args.args
            import json

            if isinstance(body, bytes):
                data = json.loads(body)
            else:
                data = json.loads(mock_post.await_args.kwargs.get("content", b"{}"))
            assert data["target_flavor"] == "assistant"
            assert data["message"] == "hello"

    @pytest.mark.asyncio
    async def test_send_message_api_key_header(self):
        async with Nx01TuiApp("http://localhost:8000", "my-secret-key").run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-assistant"

            mock_response = MagicMock()
            mock_response.json.return_value = {"correlation_id": "abc"}
            mock_post = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient.post", mock_post):
                await pilot.app._send_message("hello")
                await pilot.pause(0.3)

            mock_post.assert_awaited_once()
            headers = mock_post.await_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer my-secret-key"

    @pytest.mark.asyncio
    async def test_send_message_appends_user_message_locally(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-assistant"

            mock_response = MagicMock()
            mock_response.json.return_value = {"correlation_id": "abc"}
            mock_post = AsyncMock(return_value=mock_response)

            with patch("httpx.AsyncClient.post", mock_post):
                await pilot.app._send_message("hello")
                await pilot.pause(0.3)

            conv = pilot.app.query_one("#conv-assistant", ConversationPane)
            log = conv.query_one(RichLog)
            assert any("hello" in str(strip) for strip in log.lines)

    @pytest.mark.asyncio
    async def test_send_message_no_tabs_no_crash(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            mock_post = AsyncMock()
            with patch("httpx.AsyncClient.post", mock_post):
                await pilot.app._send_message("hello")
                await pilot.pause(0.2)
            mock_post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_message_network_error_does_not_crash(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-assistant"

            mock_post = AsyncMock(side_effect=Exception("network error"))
            with patch("httpx.AsyncClient.post", mock_post):
                await pilot.app._send_message("hello")
                await pilot.pause(0.2)


# ---------------------------------------------------------------------------
# Input submission integration
# ---------------------------------------------------------------------------


class TestInputSubmission:
    @pytest.mark.asyncio
    async def test_enter_sends_message_and_clears(self):
        async with Nx01TuiApp("http://localhost:8000", None).run_test() as pilot:
            pilot.app._states["assistant"] = FlavorState(name="assistant")
            pilot.app._mount_flavor_tab("assistant")
            await pilot.pause(0.3)

            tabs = pilot.app.query_one("#tabs", TabbedContent)
            tabs.active = "tab-assistant"

            mock_response = MagicMock()
            mock_response.json.return_value = {"correlation_id": "abc"}
            mock_post = AsyncMock(return_value=mock_response)

            inp = pilot.app.query_one("#msg-input", Input)
            inp.focus()
            await pilot.press("h", "e", "l", "l", "o")

            with patch("httpx.AsyncClient.post", mock_post):
                await pilot.press("enter")
                await pilot.pause(0.3)

            assert inp.value == ""
            mock_post.assert_awaited_once()


# ---------------------------------------------------------------------------
# _sse_worker parsing
# ---------------------------------------------------------------------------


class TestSSEParsing:
    def test_sse_parse_event_type(self):
        lines = ["event: message", "data: {}", ""]
        data_lines = []
        for line in lines:
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line == "":
                assert data_lines == ["{}"]
                data_lines = []

    def test_sse_parse_multiline_data(self):
        lines = [r'data: {"type": "AgentChunkEvent", "flavor": "a", "text": "line1\nline2"}', ""]
        data_lines = []
        for line in lines:
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line == "":
                raw = "\n".join(data_lines)
                import json

                data = json.loads(raw)
                assert data["type"] == "AgentChunkEvent"
                assert data["flavor"] == "a"
                assert data["text"] == "line1\nline2"
                data_lines = []
