# 选择官方 Python 基础镜像
FROM python:3.10-slim

# 安装FFmpeg和常用依赖
RUN apt-get update && \
    apt-get install -y ffmpeg gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app
# 先复制 requirements.txt
COPY requirements.txt /app/requirements.txt

# 再复制其它代码
COPY . /app

# 创建虚拟环境
RUN python -m venv /opt/venv

# 激活虚拟环境并安装依赖
RUN /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 设置环境变量，确保后续命令都用venv
ENV PATH="/opt/venv/bin:$PATH"

# 默认启动命令（可根据你的项目实际入口调整）
CMD ["python", "app.py"]
