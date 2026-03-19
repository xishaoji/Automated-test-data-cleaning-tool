import streamlit as st
import pandas as pd
import os
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 引入我们重构后的 LangGraph 核心大脑和数据体检工具
from core.agent import LangGraphDataAgent
from utils.data_profiler import generate_profiling_report

# --- 1. 页面与全局状态配置 ---
st.set_page_config(page_title="设备通信与测试日志分析助手", page_icon="🔌", layout="wide")
st.title("整机测试日志清洗与分析助手")

# 初始化 Session State 以保持多轮对话和状态记忆
if "messages" not in st.session_state:
    st.session_state.messages = []
if "df" not in st.session_state:
    st.session_state.df = None
if "dataset_schema" not in st.session_state:
    st.session_state.dataset_schema = ""
if "csv_file_path" not in st.session_state:
    st.session_state.csv_file_path = ""

# 确保本地有一个数据目录用于存放 Docker 沙盒需要的源文件
DATA_DIR = os.path.abspath("./data")
os.makedirs(DATA_DIR, exist_ok=True)

# --- 2. 侧边栏：数据上传与预处理 ---
with st.sidebar:
    st.header("📁 测试日志管理")
    st.caption("支持基于底层协议导出的 CSV 或 Excel 抓包文件")
    
    uploaded_file = st.file_uploader("上传整机/通信测试记录", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            # 读取数据
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.session_state.df = df
            
            # 【核心逻辑】：将文件落盘，供 Docker 沙盒内的 Python 脚本读取
            file_path = os.path.join(DATA_DIR, "current_session.csv")
            df.to_csv(file_path, index=False)
            st.session_state.csv_file_path = file_path
            
            # 提取 Schema (字段类型与前3行)，用于精确组装 Agent 的 System Prompt
            df_head = df.head(3).to_markdown()
            df_types = df.dtypes.to_string()
            st.session_state.dataset_schema = f"字段类型:\n{df_types}\n\n前三行数据预览:\n{df_head}"
            
            st.success("✅ 底层日志加载并挂载沙盒成功！")
            
            # 渲染基础数据体检报告
            st.markdown(generate_profiling_report(df))
            
            # 提供实时下载最新数据的接口（Agent 修改数据后，用户可随时导出）
            with open(file_path, "rb") as file:
                st.download_button(
                    label="📥 导出当前最新数据集",
                    data=file,
                    file_name="processed_test_log.csv",
                    mime="text/csv"
                )
                
        except Exception as e:
            st.error(f"解析文件失败: {e}")

# --- 3. 异步流式执行包装器 ---
async def process_user_query(user_query: str):
    """封装对 LangGraph 的异步调用，并在 UI 上渲染中间过程"""
    agent_core = LangGraphDataAgent()
    workflow_app = agent_core.build_graph()
    
    # 构建输入给图的初始状态
    initial_state = {
        "messages": [{"role": "user", "content": user_query}],
        "dataset_schema": st.session_state.dataset_schema,
        "csv_file_path": st.session_state.csv_file_path
    }
    
    final_response = ""
    status_container = st.empty()
    
    # 捕获 LangGraph 流转状态，展示极客感十足的思考过程
    with status_container.container():
        with st.status("🧠 Agent 正在分析日志与编写脚本...", expanded=True) as status:
            async for event in workflow_app.astream(initial_state, stream_mode="values"):
                if "messages" in event:
                    last_msg = event["messages"][-1]
                    # 如果 Agent 决定调用执行 Python 的工具
                    if getattr(last_msg, "tool_calls", None):
                        st.write(f"🛠️ **触发沙盒执行**: 正在隔离运行数据清洗代码...")
                    # 捕获最终的大模型自然语言回复
                    elif last_msg.type == "ai" and not getattr(last_msg, "tool_calls", None):
                        final_response = last_msg.content
                        st.write("✍️ **分析完成，正在生成结论...**")
            
            status.update(label="处理完成", state="complete", expanded=False)
            
    return final_response

# --- 4. 主界面：数据预览与智能交互 ---
if st.session_state.df is not None:
    # 动态数据看板
    with st.expander("🔎 实时数据预览 (前 10 行)", expanded=True):
        # 每次交互后重新从磁盘读取最新状态，确保 UI 和沙盒数据同步
        current_df = pd.read_csv(st.session_state.csv_file_path)
        st.dataframe(current_df.head(10))

    st.divider()

    # 渲染历史对话记录
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 预设工业级测试指令建议
    st.caption("💡 示例指令：'提取日志中所有包含特定指令集的报文，并将心跳包丢包率超过 5% 的设备ID整理成新表格'")
    
    # 聊天输入与触发
    if prompt := st.chat_input("输入针对该批次测试数据的分析或清洗指令..."):
        # 1. 渲染用户输入
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. 触发 Agent 核心逻辑
        with st.chat_message("assistant"):
            try:
                # Streamlit 是同步环境，使用 asyncio.run 运行图逻辑
                answer = asyncio.run(process_user_query(prompt))
                
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 强制页面刷新，以重新加载最新的 DataFrame 预览
                st.rerun()
                
            except Exception as e:
                error_msg = f"⚠️ 分析链路中断: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
else:
    st.info("👈 请先在左侧面板上传由协议文档转换出的测试 CSV 文件。")