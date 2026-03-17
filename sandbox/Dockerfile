FROM python:3.11-slim-bookworm

# 环境变量优化
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/usr/local/bin:$PATH"

WORKDIR /app

# 只安装必要依赖
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 创建低权限用户
RUN useradd -m -u 1000 sandboxuser

# 拷贝代码
COPY . .

# 设置目录权限（只允许访问 app）
RUN chown -R sandboxuser:sandboxuser /app

USER sandboxuser
CMD ["python", "script.py"]