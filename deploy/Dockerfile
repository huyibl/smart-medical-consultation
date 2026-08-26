# 同源镜像：先构建 Vue，再装 Python API。
FROM node:22-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src \
    API_HOST=0.0.0.0 \
    API_PORT=8000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /fe/dist /app/frontend/dist
EXPOSE 8000
CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8000"]
