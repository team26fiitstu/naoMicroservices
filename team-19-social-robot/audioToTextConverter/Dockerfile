FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg decodes incoming audio for whisperx
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /service

COPY requirements.txt .

# PyTorch comes from the CPU-only index, without CUDA libraries
RUN grep -E '^torch(vision|audio)?==' requirements.txt \
        | xargs pip install --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt \
    && pip uninstall -y triton

COPY . .

EXPOSE 9901

CMD ["python", "text_from_audio_extractor_service.py"]
