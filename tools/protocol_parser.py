"""Protocol parsing helpers for the industrial test-log domain.

The parser is deliberately tiny — real protocol decoding should live in its
own package with proper binary tooling. Here we expose a LangChain ``tool``
that the agent can call whenever it runs into a hex payload it does not
understand.
"""

from __future__ import annotations

from typing import Final, TypedDict

from langchain_core.tools import tool

from core.exceptions import ProtocolParseError

_MIN_PAYLOAD_LEN: Final[int] = 8  # 4 bytes: STX + CMD + ... + CRC
_CMD_TABLE: Final[dict[str, str]] = {
    "01": "Heartbeat",
    "02": "Charging_Data",
    "03": "Platform_Command",
    "04": "Alarm_Report",
}


class ParsedPayload(TypedDict):
    """Structured result returned by :func:`parse_communication_protocol`."""

    is_valid: bool
    cmd_code: str
    cmd_type: str
    data_body: str


def _parse_hex(payload: str) -> ParsedPayload:
    hex_payload = payload.strip().replace(" ", "").upper()
    if len(hex_payload) < _MIN_PAYLOAD_LEN:
        raise ProtocolParseError(f"payload too short: {len(hex_payload)} nibbles")
    if any(c not in "0123456789ABCDEF" for c in hex_payload):
        raise ProtocolParseError("payload contains non-hex characters")

    cmd_code = hex_payload[2:4]
    data_body = hex_payload[4:-4]

    return ParsedPayload(
        is_valid=True,
        cmd_code=cmd_code,
        cmd_type=_CMD_TABLE.get(cmd_code, f"Unknown(0x{cmd_code})"),
        data_body=data_body,
    )


@tool("parse_communication_protocol")
def parse_communication_protocol(hex_payload: str) -> dict:
    """Decode a single hex protocol payload (heartbeat / charge / command / alarm).

    Input is a continuous hex string (``"AA 01 ... CRC"`` or ``"AA01...CRC"``).
    The tool returns ``is_valid=False`` together with an ``error`` field when
    the payload is malformed, so the agent can decide whether to retry.
    """

    try:
        return dict(_parse_hex(hex_payload))
    except ProtocolParseError as exc:
        return {"is_valid": False, "error": str(exc)}
