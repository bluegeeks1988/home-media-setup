FROM python:3.12-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data && chown 10001:10001 /data
USER appuser
EXPOSE 3000
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "app.main:app"]
