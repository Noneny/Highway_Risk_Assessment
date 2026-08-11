FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN cp config/input_db.example.ini config/input_db.ini \
    && cp config/output_db.example.ini config/output_db.ini \
    && mkdir -p data/input/traffic_data data/input/weather_warnings data/temp data/output log

EXPOSE 8000

# 任务状态保存在进程内，且模型使用共享中间文件，因此必须保持单 worker。
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
