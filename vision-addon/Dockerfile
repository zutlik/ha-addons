FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libopenblas0 \
    ffmpeg \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .
RUN mkdir -p /data/known_faces

COPY run.sh /usr/bin/run.sh
RUN chmod +x /usr/bin/run.sh

ENV PATH=/root/.local/bin:$PATH

EXPOSE 8080

CMD ["/usr/bin/run.sh"]
