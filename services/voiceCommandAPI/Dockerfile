FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Shared modules live outside this build context (named context "common")
COPY --from=common /http_retry.py .

CMD ["python", "server.py"]
