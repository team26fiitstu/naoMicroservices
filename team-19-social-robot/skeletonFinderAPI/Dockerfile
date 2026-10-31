FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# shared libraries required by OpenCV
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /python-flask

COPY requirements.txt .

# PyTorch comes from the CPU-only index, without CUDA libraries
RUN grep -E '^torch(vision)?==' requirements.txt \
        | xargs pip install --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

ADD https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7-w6-pose.pt .

COPY server .

CMD [ "python", "server.py" ]
