# tools/protocol_parser.py
from langchain_core.tools import tool
import pandas as pd

@tool("parse_communication_protocol")
def parse_communication_protocol(hex_payload: str) -> dict:
    """
    当发现日志中包含 16 进制通信报文 (Payload) 时，调用此工具进行协议解包。
    支持解析平台交互指令、整机心跳包状态等。
    """
    try:
        if len(hex_payload) < 8:
            return {"error": "报文长度异常"}
            
        cmd_type = hex_payload[2:4]
        data_body = hex_payload[4:-4]
        
        result = {
            "is_valid": True,
            "cmd_type": "Heartbeat" if cmd_type == "01" else "Charging_Data",
            "raw_data": data_body
        }
        return result
    except Exception as e:
        return {"error": f"解析失败: {str(e)}"}