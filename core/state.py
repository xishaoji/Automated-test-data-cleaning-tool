from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class DataCopilotState(TypedDict):
    # 自动管理对话和工具调用的消息历史
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 当前分析的数据集元信息（比如列名、数据类型、前3行数据）
    # 每次新建图的时候注入，让 LLM 知道它面对的是什么数据
    dataset_schema: str 
    
    # 记录数据集所在的物理路径，方便代码沙盒去挂载和读取
    csv_file_path: str