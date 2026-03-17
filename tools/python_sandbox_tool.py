from langchain_core.tools import tool
from sandbox.container_manager import DockerSandbox

sandbox_env = DockerSandbox()

@tool("execute_python_code")
def execute_python_code(code: str, csv_path: str) -> str:
    """
    当需要对测试日志、报文或数据表进行清洗、计算、作图时，调用此工具执行 Python (Pandas) 代码。
    
    【极其重要的编码规范】：
    1. 你不需要自己凭空捏造数据，数据集已经存在于绝对路径 `/data/input.csv` 中。
    2. 你必须在代码开头写：`import pandas as pd \n df = pd.read_csv('/data/input.csv')`。
    3. 你必须使用 print() 输出你想让我看到的结果（比如 df.head() 或 统计结果），否则我什么都看不到。
    4. 如果需要覆盖修改数据，请执行 `df.to_csv('/data/output.csv', index=False)`。
    """
    try:
        print("🛠️ [Sandbox] 正在将代码送入隔离容器执行...")
        # 调用我们之前写的 Docker 沙盒执行逻辑
        result = sandbox_env.run_code_in_sandbox(code, csv_path)
        return result
    except Exception as e:
        return f"沙盒执行发生系统级异常: {str(e)}"