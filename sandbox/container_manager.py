# sandbox/container_manager.py
import docker
import os
import tempfile
from utils.logger import agent_logger

class DockerSandbox:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print("⚠️ Docker 未启动或未安装。请确保 Docker Desktop 正在运行。")
            self.client = None

    def run_code_in_sandbox(self, python_code: str, dataframe_csv_path: str) -> str:
        """
        在隔离的 Docker 容器中运行大模型生成的 Python 代码
        """
        if not self.client:
            return "Error: Docker 环境未就绪，无法安全执行代码。"
        
        agent_logger.info("准备在 Docker 沙盒中执行生成的清洗脚本。")
        # 将大模型生成的代码原封不动记录到日志，这是查 Bug 的终极武器
        agent_logger.debug(f"--- 待执行的 Python 代码 ---\n{python_code}\n-----------------------")

        # 1. 创建临时目录存放代码和数据
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "script.py")
            
            # 注入读取数据和保存结果的胶水代码
            safe_code = f"""
import pandas as pd
import sys

try:
    df = pd.read_csv('/data/input.csv')
    
    # --- LLM 生成的代码开始 ---
{python_code}
    # --- LLM 生成的代码结束 ---
    
    # 强制将处理后的数据保存回临时目录
    if 'df' in locals():
        df.to_csv('/data/output.csv', index=False)
        print("✅ 数据处理执行成功。")
except Exception as e:
    print(f"❌ 执行错误: {{str(e)}}", file=sys.stderr)
"""
            with open(script_path, "w") as f:
                f.write(safe_code)

            # 2. 启动一次性容器执行代码
            try:
                # 将外部数据和脚本挂载到容器内的 /data 和 /app
                volumes = {
                    temp_dir: {'bind': '/app', 'mode': 'ro'},
                    os.path.dirname(dataframe_csv_path): {'bind': '/data', 'mode': 'rw'}
                }
                
                # 运行手动创建像
                container = self.client.containers.run(
                    "pandas-sandbox:latest", 
                    volumes=volumes,
                    mem_limit="256m", # 严格限制内存，防止内存泄漏攻击
                    network_disabled=True, # 绝对禁止外网连接
                    remove=True, # 运行完瞬间销毁
                    stdout=True,
                    stderr=True
                )
                return container.decode('utf-8')
            except docker.errors.ContainerError as e:
                error_msg = e.stderr.decode('utf-8')
                agent_logger.error(f"沙盒执行抛出异常:\n{error_msg}")
                return f"代码沙盒执行异常: {e.stderr.decode('utf-8')}"