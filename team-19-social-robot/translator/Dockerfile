FROM python:3.11-slim

WORKDIR /app

# Install system deps if needed (none likely)
# RUN apt-get update && apt-get install -y ... 

# Copy project
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir flask requests flask-cors dotenv

ENV NO_NAMING $NO_NAMING

# Expose API port
EXPOSE 7000

# Run the service
CMD ["python", "nao_pose_service.py"]
