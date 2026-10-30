FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --system --uid 10001 app && mkdir -p /var/log/hrdocs && chown app /var/log/hrdocs
USER app
EXPOSE 8000
# --no-proxy-headers: IP client do app.net tự xác định (chỉ tin X-Forwarded-For khi request đến từ Kong)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]
