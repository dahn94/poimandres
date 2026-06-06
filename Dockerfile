FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY corpus ./corpus
RUN uv sync --frozen --no-dev
EXPOSE 8000
ENV POIMANDRES_LLM=claude
CMD ["uv", "run", "poimandres", "servir", "--porta", "8000", "--host", "0.0.0.0"]
