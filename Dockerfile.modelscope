FROM modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/python:3.10

WORKDIR /home/user/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/backend/ /home/user/app/src/backend/
COPY src/frontend/dist/ /home/user/app/src/frontend/dist/
COPY .env.example /home/user/app/.env.example
COPY app.py /home/user/app/app.py

EXPOSE 7860

ENTRYPOINT ["python", "-u", "app.py"]
