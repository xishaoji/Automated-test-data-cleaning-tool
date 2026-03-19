from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sandbox.container_manager import DockerSandbox

# 初始化 Docker 沙盒管理器
sandbox_env = DockerSandbox()

@tool("execute_python_code")
def execute_python_code(
    code: str, 
    state: Annotated[dict, InjectedState]  # 传入资料目录，大模型看不见这个参数！
) -> str:
    """
    当需要对测试日志进行清洗、计算、提取时，调用此工具执行 Python (Pandas) 代码。
    
    【💡 极其重要的沙盒编码规范】：
    1. 你【不需要】且【绝对不能】写代码去读取或保存 CSV 文件！严禁使用 pd.read_csv() 或 df.to_csv()。
    2. 全局变量 `df` (Pandas DataFrame) 已经在上下文中为你加载完毕。
    3. 你只需要直接编写对 `df` 进行逻辑处理的代码即可。
    4. 如果你想让我看到结果，请使用 `print()`。
    """
    try:
        # 从State 中，安全提取物理路径
        csv_path = state.get("csv_file_path")
        
        if not csv_path:
            return "系统错误：未能在上下文中找到当前文件路径。"
            
        print(f"🛠️ [Sandbox] 正在执行代码，目标映射文件: {csv_path} ...")
        
        # 传给底层的 Docker 胶水代码
        result = sandbox_env.run_code_in_sandbox(code, csv_path)
        return result
    except Exception as e:
        return f"Docker 沙盒执行发生系统级异常: {str(e)}"