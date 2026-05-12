"""Streamlit front-end for the test-log copilot."""

from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from core.agent import LangGraphDataAgent
from core.config import get_settings
from utils.data_profiler import generate_profiling_report
from utils.logger import get_logger

logger = get_logger("ui")
settings = get_settings()

DATA_DIR = Path("./data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="设备通信与测试日志分析助手", page_icon="🔌", layout="wide")
st.title("整机测试日志清洗与分析助手")

# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "messages": [],
    "df": None,
    "dataset_schema": "",
    "csv_file_path": "",
    "session_id": uuid.uuid4().hex[:8],
    "agent_graph": None,
}
for key, default in _DEFAULTS.items():
    st.session_state.setdefault(key, default)


def _get_graph():
    """Compile the LangGraph workflow lazily and cache it for the session."""

    if st.session_state.agent_graph is None:
        st.session_state.agent_graph = LangGraphDataAgent().build_graph()
    return st.session_state.agent_graph


def _session_csv_path() -> Path:
    # Per-session file avoids concurrent users stomping on each other.
    return DATA_DIR / f"session_{st.session_state.session_id}.csv"


# ---------------------------------------------------------------------------
# Sidebar — data upload
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📁 测试日志管理")
    st.caption(
        f"支持 CSV / Excel，单文件上限 {settings.max_upload_mb} MB。"
    )

    uploaded_file = st.file_uploader(
        "上传整机/通信测试记录", type=["csv", "xlsx"], key="uploader"
    )

    if uploaded_file is not None:
        size_mb = uploaded_file.size / (1024 * 1024)
        if size_mb > settings.max_upload_mb:
            st.error(
                f"文件过大 ({size_mb:.1f} MB)，当前上限为 {settings.max_upload_mb} MB。"
            )
        else:
            try:
                raw_bytes = uploaded_file.getvalue()
                if uploaded_file.name.lower().endswith(".csv"):
                    df = pd.read_csv(io.BytesIO(raw_bytes))
                else:
                    df = pd.read_excel(io.BytesIO(raw_bytes))

                csv_path = _session_csv_path()
                df.to_csv(csv_path, index=False)

                st.session_state.df = df
                st.session_state.csv_file_path = str(csv_path)
                st.session_state.dataset_schema = (
                    f"字段类型:\n{df.dtypes.to_string()}\n\n"
                    f"前三行数据预览:\n{df.head(3).to_markdown(index=False)}"
                )

                st.success("✅ 日志已加载并挂载到沙盒目录")
                st.markdown(generate_profiling_report(df))
                st.download_button(
                    "📥 导出当前最新数据集",
                    data=csv_path.read_bytes(),
                    file_name="processed_test_log.csv",
                    mime="text/csv",
                )
            except Exception as exc:  # noqa: BLE001 — surface any parse issue to the UI
                logger.exception("failed to parse uploaded file")
                st.error(f"解析文件失败: {exc}")


# ---------------------------------------------------------------------------
# Async workflow driver
# ---------------------------------------------------------------------------


async def _process_user_query(user_query: str) -> str:
    graph = _get_graph()
    initial_state = {
        "messages": [{"role": "user", "content": user_query}],
        "dataset_schema": st.session_state.dataset_schema,
        "csv_file_path": st.session_state.csv_file_path,
    }

    final_response = ""
    with st.status("🧠 Agent 正在分析日志与编写脚本...", expanded=True) as status:
        async for event in graph.astream(initial_state, stream_mode="values"):
            messages = event.get("messages")
            if not messages:
                continue
            last = messages[-1]
            if getattr(last, "tool_calls", None):
                st.write("🛠️ **触发沙盒执行**: 正在隔离运行数据清洗代码...")
            elif getattr(last, "type", "") == "ai":
                final_response = getattr(last, "content", "") or ""
                st.write("✍️ **分析完成，正在生成结论...**")
        status.update(label="处理完成", state="complete", expanded=False)

    return final_response


# ---------------------------------------------------------------------------
# Main column — preview + chat
# ---------------------------------------------------------------------------

if st.session_state.df is not None:
    with st.expander("🔎 实时数据预览 (前 10 行)", expanded=True):
        current_df = pd.read_csv(st.session_state.csv_file_path)
        st.dataframe(current_df.head(10), width="stretch")

    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    st.caption(
        "💡 示例指令: '提取心跳包丢包率超过 5% 的设备ID，生成清单并给出丢包时间分布。'"
    )

    if prompt := st.chat_input("输入针对该批次测试数据的分析或清洗指令..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                answer = asyncio.run(_process_user_query(prompt))
                answer = answer or "未能从模型取得最终结论，请查看日志或重试。"
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                logger.exception("agent turn failed")
                error_msg = f"⚠️ 分析链路中断: {exc}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
else:
    st.info("👈 请先在左侧面板上传由协议文档转换出的测试 CSV 文件。")
