# GStreamer Pyannote

Real-time speaker diarization GStreamer element powered by pyannote-audio.

## Overview

`gst-pyannote` provides a GStreamer element that performs speaker diarization on live audio streams. It accepts audio from sources like WebRTC, PipeWire, or any GStreamer audio source and outputs JSON-formatted diarization events.

## Features

- **Real-time Processing**: Stream audio through with minimal latency
- **Multiple Input Sources**: WebRTC, PipeWire, files, or any GStreamer source
- **JSON Output**: Structured speaker diarization events with timestamps
- **Dynamic Control**: Load/unload models and adjust parameters on-the-fly
- **Rich Signaling**: Comprehensive event system for monitoring and control

## Installation

```bash
# Development installation
pip install -e ".[dev]"
```

## Quick Start

```bash
# Basic pipeline
gst-launch-1.0 \
    filesrc location=audio.wav ! \
    decodebin ! \
    audioconvert ! \
    gstpyannote model-name="pyannote/speaker-diarization-3.1" ! \
    filesink location=diarization.json
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           GstPyannote Element               │
│                                             │
│  Audio In → Buffer → Inference → JSON Out  │
│                ↓                            │
│           Control Pad                       │
└─────────────────────────────────────────────┘
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=gst_pyannote --cov-report=html

# Run only unit tests
pytest -m unit

# Run integration tests (requires GStreamer)
pytest -m integration
```

## Project Status

This project is in active development. See the [implementation plan](docs/IMPLEMENTATION_PLAN.md) for details.

## License

MIT License - see LICENSE file for details.
