FROM python:3.11-slim

WORKDIR /app

# Install system deps if needed (none likely)
# RUN apt-get update && apt-get install -y ... 

# Copy project
COPY . .

# Shared modules live outside this build context (named context "common")
COPY --from=common /http_retry.py .

# Install Python dependencies
RUN pip install --no-cache-dir flask requests flask-cors python-dotenv==0.17.1


# Expose API port
EXPOSE 7000

# Run the service
CMD ["python", "nao_pose_service.py"]
