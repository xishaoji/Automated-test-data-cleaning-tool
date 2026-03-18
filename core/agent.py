from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from core.state import DataCopilotState
from utils.logger import agent_logger

# 💡 引入我们写的两个核心工具
from tools.python_sandbox_tool import execute_python_code
from tools.protocol_parser import parse_communication_protocol 

class LangGraphDataAgent:
    def __init__(self, model_name="deepseek-chat"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        
        # 💡 【关键修正】：将沙盒执行器和协议解析器同时赋予大模型
        self.tools = [execute_python_code, parse_communication_protocol]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def _get_system_prompt(self, schema: str, file_path: str) -> str:
        
        return f"""你是一个顶级的设备通信日志分析专家。
你的任务是清理、分析和洞察底层硬件测试日志。
        
【当前数据集信息】：
文件路径变量: {file_path}
数据结构与前3行预览：
{schema}

【核心工作流与工具使用规范】：
1. 遇到难以理解的 16 进制报文 (Hex Payload) 时，先调用 `parse_communication_protocol` 工具，传入单条报文进行解码测试，理解其含义。
2. 理解报文结构后，调用 `execute_python_code` 工具，编写 Pandas 代码对整个 CSV 文件进行批量清洗和计算。
3. 如果代码沙盒执行报错，请仔细阅读错误日志，修复代码并重新调用 `execute_python_code`。
4. 拿到最终正确的数据后，用自然语言向测试人员总结你的诊断结论。"""

    # ... (后续的 _check_infinite_loop 和 reasoner_node 保持上一版的逻辑不变) ...

    def _check_infinite_loop(self, messages) -> bool:
        """扫描近期消息，判断是否陷入了连续报错死循环"""
        error_count = 0
        # 倒序检查最近的对话
        for msg in reversed(messages):
            if msg.type == "tool":
                # 如果工具返回了包含“异常”或“Error”的字符串
                if "异常" in msg.content or "Error" in msg.content or "Exception" in msg.content:
                    error_count += 1
                else:
                    break # 遇到一次成功的执行，就清零打断
            elif msg.type == "user":
                break # 遇到人类的新指令，重新计算
                
        return error_count >= 3

    async def reasoner_node(self, state: DataCopilotState):
        """核心思考节点"""
        messages = state["messages"]
        
        # 1. 触发熔断机制：如果连续报错 3 次，强制停止调用工具，向人类求助
        if self._check_infinite_loop(messages):
            print("🚨 [熔断触发] Agent 已陷入报错死循环，请求人类介入！")
            agent_logger.warning("🚨 触发熔断：Agent 已陷入报错死循环，请求人类介入。")
            sos_msg = AIMessage(content="⚠️ **执行熔断**：我尝试了 3 次修复清洗脚本，但在处理这批特殊的底层日志时依然报错。人类专家，请帮我检查一下是不是特定的 16 进制字段名有误，或者给我更明确的代码编写提示？")
            return {"messages": [sos_msg]}
        
        agent_logger.info("开始进行 Graph 状态流转与推理...")
        # 2. 正常逻辑：动态组装包含数据表 Schema 的系统提示词
        sys_prompt = self._get_system_prompt(state["dataset_schema"], state["csv_file_path"])
        full_messages = [SystemMessage(content=sys_prompt)] + messages
        
        print("🧠 [Agent] 正在思考并生成执行方案...")
        response = await self.llm_with_tools.ainvoke(full_messages)
        if getattr(response, "tool_calls", None):
            agent_logger.debug(f"模型决定调用工具: {response.tool_calls}")
        agent_logger.info("推理完成，准备返回结果...")
        return {"messages": [response]}

    def build_graph(self):
        """编译状态机工作流"""
        workflow = StateGraph(DataCopilotState)
        
        # 1. 注册核心推理节点
        workflow.add_node("reasoner", self.reasoner_node)
        
        # 2. 注册工具执行节点 (官方现成模块，自动处理工具参数注入)
        tool_node = ToolNode(self.tools)
        workflow.add_node("tools", tool_node)
        
        # 3. 编排边 (Edges) 与路由
        workflow.add_edge(START, "reasoner")
        
        # 如果 reasoner 输出了工具调用 -> 去 tools 节点；否则 -> 结束
        workflow.add_conditional_edges(
            "reasoner",
            tools_condition,
            {
                "tools": "tools",
                END: END
            }
        )
        
        # 工具执行完毕后，必须把打印结果（或者报错）带回给 reasoner 进行评估
        workflow.add_edge("tools", "reasoner")
        
        # 编译 Graph (可接入 SqliteSaver 实现记忆)
        return workflow.compile()