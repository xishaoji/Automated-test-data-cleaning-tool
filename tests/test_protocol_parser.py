"""Tests for tools.protocol_parser — validates hex payload decoding."""

from __future__ import annotations

import pytest

from core.exceptions import ProtocolParseError
from tools.protocol_parser import _parse_hex, parse_communication_protocol


class TestParseHex:
    """Unit tests for the internal _parse_hex function."""

    def test_heartbeat(self):
        # STX(AA) + CMD(01) + 4 nibbles data + CRC(2 bytes = 4 nibbles)
        result = _parse_hex("AA01DEADBEEF1234")
        assert result["is_valid"] is True
        assert result["cmd_type"] == "Heartbeat"
        assert result["cmd_code"] == "01"
        assert result["data_body"] == "DEADBEEF"

    def test_charging_data(self):
        result = _parse_hex("AA02AABBCCDD1234")
        assert result["cmd_type"] == "Charging_Data"

    def test_unknown_command(self):
        result = _parse_hex("AAFF112233441234")
        assert "Unknown" in result["cmd_type"]

    def test_too_short_raises(self):
        with pytest.raises(ProtocolParseError, match="too short"):
            _parse_hex("AA01")

    def test_non_hex_raises(self):
        with pytest.raises(ProtocolParseError, match="non-hex"):
            _parse_hex("GGHHIIJJKKLL")

    def test_spaces_stripped(self):
        result = _parse_hex("AA 01 DE AD BE EF 12 34")
        assert result["is_valid"] is True


class TestToolInterface:
    """Ensure the @tool-decorated function returns dict (not raises)."""

    def test_valid_payload_returns_dict(self):
        out = parse_communication_protocol.invoke({"hex_payload": "AA01DEADBEEF1234"})
        assert out["is_valid"] is True

    def test_invalid_payload_returns_error(self):
        out = parse_communication_protocol.invoke({"hex_payload": "AB"})
        assert out["is_valid"] is False
        assert "error" in out
