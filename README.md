Markdown
# 测试日志分析平台

本项目是一个基于 **LangGraph** 构建的生产级数据清洗与分析 Agent 框架，专为解决工业设备（如充电桩）底层通信协议测试、整机日志排查而设计。
使用 **Docker 沙盒物理隔离**技术，可安全的执行模型生成的代码，替代传统测试工程师排查丢包、时序异常与报文解析的工作模式。

## ✨ 核心特性 (Key Features)

* **🧠 状态机驱动的智能体大脑**：基于 LangGraph 重构逻辑链路，支持动态工具路由、错误捕获与自主修复。
* **🛡️ Docker 沙盒级代码执行**：LLM 生成的 Pandas 清洗代码将在无外网、受限资源的临时容器中隔离执行，保障宿主机与核心业务数据的绝对安全。
* **🔌 深度协议解析双核引擎**：
  * **协议解包器**：内置定制化 16 进制通信报文（Hex Payload）解析工具。
  * **代码沙盒**：大模型可自主实现“先解析底层指令 -> 再生成批处理代码”的复杂跨步骤推理。
* **🚨 柔性熔断与人工介入 (Human-in-the-loop)**：内置无限循环保护机制，当 Agent 连续 3 次执行代码失败时，自动熔断并向前端请求人类专家援助。

## 🏗️ 系统架构 (Architecture)

```text
agentic-test-log-copilot/
├── app.py                    # 主程序入口
├── core/                     # 核心逻辑
│   ├── state.py              # 图状态定义 (TypedDict & InjectedState)
│   ├── agent.py              # LangGraph 节点编排与路由
│   └── prompts.py            
├── tools/                    # 扩展层：自定义工具集
│   ├── python_sandbox_tool.py# 封装 Docker 代码执行工具
│   └── protocol_parser.py    # 底层通信协议 16 进制解析器
├── sandbox/                  # 安全层：沙盒执行环境
│   ├── Dockerfile            # 沙盒 Python 执行镜像配置
│   └── container_manager.py  
├── utils/                    
│   ├── logger.py             # 日志记录
│   └── data_profiler.py      # 测试日志全量数据
├── data/                     # 数据挂载层 (与前端、容器共享)
├── docker-compose.yml        # DooD (Docker-out-of-Docker) 编排文件
├── Dockerfile                # 主应用 Web 服务镜像
└── requirements.txt
```
## 🚀 快速启动 (Getting Started)
1. 环境准备
确保你的计算机或服务器已安装 Python 3.10+ 与 Docker Desktop。

2. 克隆与配置
```Bash
git clone https://github.com/xishaoji/Automated-test-data-cleaning-tool.git
cd Automated-test-data-cleaning-tool
```
配置环境变量
.env 中大模型秘钥 (如 OPENAI_API_KEY=sk-...)

3. 构建底层安全沙盒镜像
（首次运行必须）构建供大模型执行生成代码的隔离环境：

```Bash
docker build -t pandas-sandbox:latest -f sandbox/Dockerfile .
```
4. 启动服务 (双重选择)
方式 A：容器化一键部署

```Bash
docker-compose up -d
```
访问 http://localhost:8501 即可打开前端。

方式 B：本地开发调试模式

```Bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```