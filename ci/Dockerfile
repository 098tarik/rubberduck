FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir .

COPY main.py ./
COPY index.html ./
COPY app ./app
COPY assets ./assets

ENV OLLAMA_URL=http://host.docker.internal:11434
ENV OLLAMA_MODEL=deepseek-r1:8b

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]