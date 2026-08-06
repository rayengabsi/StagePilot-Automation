from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.cli.commands import _build_parser


def test_parser_exposes_agent_command() -> None:
    parser = _build_parser()
    args = parser.parse_args(["agent", "--message", "help"])
    assert args.command == "agent"
    assert hasattr(args, "handler")
    assert args.message == "help"


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_agent_single_message_handler(
    mock_factory: MagicMock, mock_engine: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli.commands import _handle_agent

    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session

    args = MagicMock()
    args.message = "help"
    args.json = True

    result = _handle_agent(args, MagicMock())
    assert result == 0
    captured = capsys.readouterr().out
    assert '"intent": "help"' in captured
    assert session.close.called
