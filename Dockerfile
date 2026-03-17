# /Dockerfile (主应用镜像)
FROM python:3.11-slim-bookworm

WORKDIR /app

# 安装必要的系统依赖和 Docker 客户端（以便 Python 能够调用宿主机的 Docker）
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将项目代码拷贝进容器
COPY . .

# 暴露 Streamlit 的默认端口
EXPOSE 8501

# 启动 Web 服务
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]