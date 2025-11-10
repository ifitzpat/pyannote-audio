# GStreamer Pyannote Deployment Guide

Production deployment guide for the GStreamer Pyannote element.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Production Configuration](#production-configuration)
- [Performance Optimization](#performance-optimization)
- [Monitoring](#monitoring)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Best Practices](#best-practices)
- [Security](#security)

---

## System Requirements

### Minimum Requirements

- **CPU**: 4 cores, 2.5 GHz
- **RAM**: 8 GB
- **Storage**: 10 GB (for models and cache)
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.8+
- **GStreamer**: 1.16+

### Recommended for Real-Time

- **CPU**: 8+ cores, 3.0+ GHz
- **GPU**: NVIDIA GPU with 4+ GB VRAM (CUDA 11+)
- **RAM**: 16 GB
- **Storage**: SSD with 20+ GB
- **Network**: Low-latency (for WebRTC)

### Software Dependencies

```bash
# GStreamer
sudo apt-get install \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gst-1.0 \
    gir1.2-gst-plugins-base-1.0

# PyTorch (CPU)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# PyTorch (GPU)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Pyannote
pip install pyannote-audio

# Development tools
pip install pytest pytest-cov pytest-mock
```

---

## Installation

### From Source

```bash
# Clone repository
git clone https://github.com/yourusername/gst-pyannote.git
cd gst-pyannote

# Install in development mode
pip install -e .

# Or install for production
pip install .

# Verify installation
python3 -c "import gst_pyannote; print(gst_pyannote.__version__)"
```

### System-Wide Installation

```bash
# Install to system Python
sudo pip install .

# Verify GStreamer can find the plugin
gst-inspect-1.0 pyannote
```

### Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install .

# Run application
python your_app.py
```

---

## Production Configuration

### Environment Variables

```bash
# GStreamer
export GST_PLUGIN_PATH=/path/to/gst-pyannote
export GST_DEBUG=2  # Minimal logging in production

# PyTorch
export CUDA_VISIBLE_DEVICES=0  # Use first GPU
export OMP_NUM_THREADS=4  # CPU thread limit

# Hugging Face (for model downloads)
export HF_HOME=/var/cache/huggingface  # Cache directory
export HF_TOKEN=hf_your_token_here  # Auth token

# Python
export PYTHONUNBUFFERED=1  # Unbuffered output for logging
```

### Configuration File

Create `config.yaml`:

```yaml
pyannote:
  model:
    name: "pyannote/speaker-diarization-3.1"
    device: "cuda"  # or "cpu"
    cache_dir: "/var/cache/pyannote"

  processing:
    window_duration: 30.0
    overlap_duration: 5.0
    low_latency: false

  inference:
    queue_size: 10
    batch_size: 1

  webrtc:
    enabled: true
    jitter_latency: 100  # ms
    plc_enabled: true

logging:
  level: "INFO"
  file: "/var/log/pyannote/application.log"
  max_size: "100MB"
  rotation: 5
```

Load configuration:

```python
import yaml

with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Apply configuration
pyannote.set_property('model-name', config['pyannote']['model']['name'])
pyannote.set_property('device', config['pyannote']['model']['device'])
pyannote.set_property('window-duration', config['pyannote']['processing']['window_duration'])
```

---

## Performance Optimization

### GPU Optimization

```python
import torch

# Enable GPU optimizations
torch.backends.cudnn.benchmark = True
torch.backends.cudnn.enabled = True

# Set device
device = 'cuda:0'
pyannote.set_property('device', device)

# Monitor GPU usage
import nvidia_smi

nvidia_smi.nvmlInit()
handle = nvidia_smi.nvmlDeviceGetHandleByIndex(0)

def check_gpu():
    info = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
    print(f"GPU Memory: {info.used / 1024**2:.0f}MB / {info.total / 1024**2:.0f}MB")
```

### CPU Optimization

```bash
# Set CPU affinity
taskset -c 0-7 python app.py

# Limit OMP threads
export OMP_NUM_THREADS=4

# Use performance governor
sudo cpupower frequency-set -g performance
```

### Memory Optimization

```python
# Reduce window size
pyannote.set_property('window-duration', 15.0)  # vs 30.0

# Limit queue size
worker = InferenceWorker(manager, max_queue_size=3)  # vs 10

# Clear cache periodically
import torch
torch.cuda.empty_cache()  # GPU
import gc
gc.collect()  # Python
```

### Network Optimization (WebRTC)

```python
# Low-latency configuration
handler = WebRTCHandler(low_latency=True)
handler.set_jitter_latency(20)  # 20ms

# Pipeline optimization
pipeline = Gst.parse_launch("""
    webrtcbin name=webrtc latency=20 !
    queue max-size-buffers=10 max-size-time=200000000 !
    rtpopusdepay !
    opusdec plc=true !
    audioconvert !
    pyannote low-latency=true window-duration=10.0 !
    fakesink sync=false
""")
```

---

## Monitoring

### Metrics Collection

```python
import prometheus_client as prom

# Define metrics
inference_duration = prom.Histogram(
    'pyannote_inference_duration_seconds',
    'Time spent in inference'
)

speakers_detected = prom.Counter(
    'pyannote_speakers_detected_total',
    'Total speakers detected'
)

packet_loss_rate = prom.Gauge(
    'webrtc_packet_loss_rate',
    'WebRTC packet loss rate'
)

# Collect metrics
@inference_duration.time()
def process_audio(audio):
    return manager.process_audio(audio, 16000, 0.0)

def on_speaker_detected(speaker, start, end):
    speakers_detected.inc()

# WebRTC stats
stats = webrtc_handler.get_statistics()
packet_loss_rate.set(stats['loss_rate'])

# Expose metrics
prom.start_http_server(8000)
```

### Health Checks

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health_check():
    # Check model loaded
    if not manager.is_loaded():
        return jsonify({'status': 'unhealthy', 'reason': 'model not loaded'}), 503

    # Check worker running
    if not worker.running:
        return jsonify({'status': 'unhealthy', 'reason': 'worker not running'}), 503

    # Check queue size
    queue_size = worker.get_queue_size()
    if queue_size > 50:
        return jsonify({'status': 'degraded', 'reason': 'high queue size'}), 200

    return jsonify({'status': 'healthy'}), 200

@app.route('/metrics')
def metrics():
    stats = {
        'model_loaded': manager.is_loaded(),
        'worker_running': worker.running,
        'queue_size': worker.get_queue_size(),
    }

    if webrtc_handler:
        stats['webrtc'] = webrtc_handler.get_statistics()

    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Logging

```python
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logger = logging.getLogger('pyannote')
logger.setLevel(logging.INFO)

# File handler with rotation
handler = RotatingFileHandler(
    '/var/log/pyannote/app.log',
    maxBytes=100*1024*1024,  # 100MB
    backupCount=5
)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Log events
logger.info('Model loaded: %s', model_name)
logger.warning('High packet loss: %.1f%%', stats['loss_rate'] * 100)
logger.error('Inference failed: %s', str(error))
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    python3-gst-1.0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Install gst-pyannote
COPY . /app/gst-pyannote
WORKDIR /app/gst-pyannote
RUN pip3 install --no-cache-dir .

# Create cache directory
RUN mkdir -p /var/cache/pyannote && \
    chmod 777 /var/cache/pyannote

# Set environment
ENV GST_PLUGIN_PATH=/app/gst-pyannote
ENV HF_HOME=/var/cache/pyannote
ENV CUDA_VISIBLE_DEVICES=0

# Expose ports
EXPOSE 8080 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["python3", "app.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  pyannote:
    build: .
    runtime: nvidia
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - HF_TOKEN=${HF_TOKEN}
      - GST_DEBUG=2
    volumes:
      - ./config.yaml:/app/config.yaml
      - pyannote-cache:/var/cache/pyannote
      - ./logs:/var/log/pyannote
    ports:
      - "8080:8080"  # API
      - "8000:8000"  # Metrics
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  pyannote-cache:
```

### Build and Run

```bash
# Build image
docker build -t gst-pyannote:latest .

# Run container
docker run -d \
    --name pyannote \
    --gpus all \
    -p 8080:8080 \
    -v $(pwd)/config.yaml:/app/config.yaml \
    -e HF_TOKEN=hf_your_token \
    gst-pyannote:latest

# Check logs
docker logs -f pyannote

# Check health
curl http://localhost:8080/health
```

---

## Kubernetes Deployment

### Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gst-pyannote
  labels:
    app: gst-pyannote
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gst-pyannote
  template:
    metadata:
      labels:
        app: gst-pyannote
    spec:
      containers:
      - name: pyannote
        image: gst-pyannote:latest
        resources:
          requests:
            memory: "8Gi"
            cpu: "4"
            nvidia.com/gpu: 1
          limits:
            memory: "16Gi"
            cpu: "8"
            nvidia.com/gpu: 1
        ports:
        - containerPort: 8080
          name: api
        - containerPort: 8000
          name: metrics
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: huggingface-token
              key: token
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: cache
          mountPath: /var/cache/pyannote
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: pyannote-config
      - name: cache
        persistentVolumeClaim:
          claimName: pyannote-cache

---
apiVersion: v1
kind: Service
metadata:
  name: gst-pyannote
spec:
  selector:
    app: gst-pyannote
  ports:
  - name: api
    port: 80
    targetPort: 8080
  - name: metrics
    port: 8000
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: pyannote-config
data:
  config.yaml: |
    pyannote:
      model:
        name: "pyannote/speaker-diarization-3.1"
        device: "cuda"
      processing:
        window_duration: 30.0
        overlap_duration: 5.0
        low_latency: false

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pyannote-cache
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
```

### Deploy

```bash
# Create secret
kubectl create secret generic huggingface-token \
    --from-literal=token=hf_your_token

# Apply manifests
kubectl apply -f deployment.yaml

# Check status
kubectl get pods -l app=gst-pyannote
kubectl logs -f deployment/gst-pyannote

# Check service
kubectl get svc gst-pyannote
```

---

## Best Practices

### 1. Model Caching

```python
# Pre-download models
import torch
from pyannote.audio import Pipeline

# Download during build/init
pipeline = Pipeline.from_pretrained(
    'pyannote/speaker-diarization-3.1',
    cache_dir='/var/cache/pyannote'
)
```

### 2. Graceful Shutdown

```python
import signal
import sys

def signal_handler(sig, frame):
    print('Gracefully shutting down...')

    # Stop worker
    worker.stop()

    # Stop pipeline
    pipeline.set_state(Gst.State.NULL)

    # Exit
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

### 3. Error Recovery

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def load_model_with_retry():
    try:
        manager.load_pipeline(model_name, use_auth_token=token)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise
```

### 4. Resource Limits

```python
# Limit memory
import resource

# Set memory limit (8GB)
resource.setrlimit(
    resource.RLIMIT_AS,
    (8 * 1024 * 1024 * 1024, -1)
)

# Limit CPU time
resource.setrlimit(
    resource.RLIMIT_CPU,
    (3600, -1)  # 1 hour
)
```

### 5. Monitoring and Alerts

```python
# Alert on high error rate
error_count = 0
error_threshold = 10

def on_error(message, error_type):
    global error_count
    error_count += 1

    if error_count >= error_threshold:
        # Send alert
        send_alert(f"High error rate: {error_count} errors")
        error_count = 0
```

---

## Security

### 1. API Authentication

```python
from flask import request, abort
import hashlib

API_KEY_HASH = hashlib.sha256(b'your-secret-key').hexdigest()

@app.before_request
def authenticate():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        abort(401)

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if key_hash != API_KEY_HASH:
        abort(403)
```

### 2. Input Validation

```python
def validate_audio_input(buffer):
    # Check size
    max_size = 10 * 1024 * 1024  # 10MB
    if buffer.get_size() > max_size:
        raise ValueError("Audio buffer too large")

    # Check format
    caps = buffer.get_caps()
    if not caps.is_subset(ALLOWED_CAPS):
        raise ValueError("Invalid audio format")
```

### 3. Rate Limiting

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

@app.route('/process')
@limiter.limit("10 per minute")
def process_audio():
    # Process audio
    pass
```

### 4. Secrets Management

```bash
# Use environment variables
export HF_TOKEN=$(vault kv get -field=token secret/huggingface)

# Or use Kubernetes secrets
kubectl create secret generic huggingface-token \
    --from-literal=token=$(vault kv get -field=token secret/huggingface)
```

---

## Production Checklist

- [ ] GPU drivers installed (if using GPU)
- [ ] Models pre-downloaded to cache
- [ ] Configuration file created
- [ ] Logging configured with rotation
- [ ] Health check endpoint implemented
- [ ] Metrics collection configured
- [ ] Error handling and recovery in place
- [ ] Resource limits configured
- [ ] Authentication enabled
- [ ] HTTPS/TLS configured (for API)
- [ ] Monitoring and alerting set up
- [ ] Backup and disaster recovery plan
- [ ] Load testing completed
- [ ] Documentation updated

---

## Support

For production support:
- Documentation: [docs/](.)
- Issues: GitHub Issues
- Security: security@example.com

---

## Updates

Keep the system updated:

```bash
# Update gst-pyannote
pip install --upgrade gst-pyannote

# Update PyTorch
pip install --upgrade torch torchaudio

# Update pyannote-audio
pip install --upgrade pyannote-audio

# Check for model updates
# (new models may have better accuracy/performance)
```
