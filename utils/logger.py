# utils/logger.py
import logging
import os
from datetime import datetime

def setup_logger():
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    # 每天生成一个新的日志文件，方便排查不同批次的测试任务
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = f"logs/agent_trace_{date_str}.log"

    logger = logging.getLogger("CopilotAgent")
    logger.setLevel(logging.DEBUG) # 捕获所有级别的日志
    
    # 防止重复挂载 handler
    if not logger.handlers:
        # 1. 文件处理器：记录所有极度详细的 DEBUG 信息（大模型写的每一行代码）
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(module)s:%(lineno)d] - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # 2. 控制台处理器：只输出 INFO 以上的骨干信息
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('🤖 %(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

# 暴露出单例 logger 供全局使用
agent_logger = setup_logger()