FROM python:3.11-slim

# Working directory inside the container
WORKDIR /service
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

# Install dependencies first (Docker layer cache — only re-runs if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# exercises folder lives inside the service — no volume mount needed
#RUN mkdir -p /service/exercises

ENV NO_NAMING $NO_NAMING

EXPOSE 9901

# Use gunicorn in production, not Flask dev server
CMD ["gunicorn", "--bind", "0.0.0.0:9901", "--workers", "2", "--timeout", "120", "run:app"]