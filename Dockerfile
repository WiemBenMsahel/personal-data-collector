FROM python:3.12-slim
WORKDIR /app
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY src ./src
COPY config ./config
ENTRYPOINT ["python", "src/pipeline.py"]