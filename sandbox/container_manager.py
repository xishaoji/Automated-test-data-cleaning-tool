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
            agent_logger.error(f"Docker 未启动或未安装: {e}")
            self.client = None

    def run_code_in_sandbox(self, python_code: str, dataframe_csv_path: str) -> str:
        """
        在隔离的 Docker 容器中运行代码，并动态同步数据文件
        """
        agent_logger.info("准备在 Docker 沙盒中执行清洗脚本。")
        agent_logger.debug(f"--- 待执行的 Python 代码 ---\n{python_code}\n-----------------------")
        
        if not self.client:
            return "Error: Docker 环境未就绪，无法安全执行代码。"

        # 💡 动态获取传进来的真实文件名 (例如 'current_session.csv')
        filename = os.path.basename(dataframe_csv_path)
        data_dir = os.path.dirname(dataframe_csv_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "script.py")
            safe_code = f"""
import pandas as pd
import sys

try:
    # 动态读取映射到容器内的真实文件
    df = pd.read_csv('/data/{filename}')
    
    # --- LLM 生成的核心业务代码开始 ---
{python_code}
    # --- LLM 生成的核心业务代码结束 ---
    
    # 强制将处理后的数据覆盖原文件，实现与外部 UI 的数据实时同步
    if 'df' in locals():
        df.to_csv('/data/{filename}', index=False)
        print("✅ 数据处理沙盒执行成功，结果已同步回宿主机。")
except Exception as e:
    print(f"❌ 执行错误: {{str(e)}}", file=sys.stderr)
"""
            with open(script_path, "w") as f:
                f.write(safe_code)

            try:
                # 将外部的脚本和真实的数据目录挂载进去
                volumes = {
                    temp_dir: {'bind': '/app', 'mode': 'ro'},
                    # 将宿主机的 data 目录映射到容器的 /data 目录，支持读写
                    os.path.abspath(data_dir): {'bind': '/data', 'mode': 'rw'} 
                }
                
                # 启动一次性沙盒
                container = self.client.containers.run(
                    "pandas-sandbox:latest", 
                    volumes=volumes,
                    mem_limit="256m", 
                    network_disabled=True, 
                    remove=True, 
                    stdout=True,
                    stderr=True
                )
                return container.decode('utf-8')
            except docker.errors.ContainerError as e:
                error_msg = e.stderr.decode('utf-8')
                agent_logger.error(f"沙盒执行抛出异常:\n{error_msg}")
                return f"沙盒执行异常: {error_msg}"