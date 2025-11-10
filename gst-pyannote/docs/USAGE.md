# GStreamer Pyannote Usage Guide

Comprehensive guide with examples for using the GStreamer Pyannote element.

## Table of Contents

- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [WebRTC Integration](#webrtc-integration)
- [Control Interface](#control-interface)
- [Signal Handling](#signal-handling)
- [Advanced Examples](#advanced-examples)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
cd gst-pyannote
pip install -e .
```

### Minimal Example

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

# Create pipeline
pipeline = Gst.parse_launch("""
    filesrc location=audio.wav !
    decodebin !
    audioconvert !
    audioresample !
    pyannote model-name=pyannote/speaker-diarization-3.1 !
    fakesink dump=true
""")

# Run
pipeline.set_state(Gst.State.PLAYING)

loop = GLib.MainLoop()
try:
    loop.run()
except KeyboardInterrupt:
    pass
finally:
    pipeline.set_state(Gst.State.NULL)
```

---

## Basic Usage

### File Processing

Process audio file and save JSON output:

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import sys

def main(input_file, output_file):
    Gst.init(None)

    # Create pipeline
    pipeline = Gst.parse_launch(f"""
        filesrc location={input_file} !
        decodebin !
        audioconvert !
        audioresample !
        audio/x-raw,rate=16000,channels=1 !
        pyannote name=diarization
            model-name=pyannote/speaker-diarization-3.1
            window-duration=30.0
            overlap-duration=5.0 !
        filesink location={output_file}
    """)

    # Handle bus messages
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}", file=sys.stderr)
            loop.quit()
        elif t == Gst.MessageType.EOS:
            print("Processing complete!")
            loop.quit()
        elif t == Gst.MessageType.ELEMENT:
            structure = message.get_structure()
            if structure.get_name() == 'pyannote-inference-complete':
                speaker_count = structure.get_int('speaker_count')[1]
                print(f"Detected {speaker_count} speakers")

    bus.connect('message', on_message)

    # Run
    print(f"Processing {input_file}...")
    pipeline.set_state(Gst.State.PLAYING)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.wav> <output.json>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
```

### Microphone Input

Real-time processing from microphone:

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

# Create pipeline with microphone input
pipeline = Gst.parse_launch("""
    pulsesrc !
    audioconvert !
    audioresample !
    audio/x-raw,rate=16000,channels=1,format=F32LE !
    pyannote name=diarization
        model-name=pyannote/speaker-diarization-3.1
        low-latency=true
        window-duration=10.0
        overlap-duration=2.0 !
    fakesink
""")

# Get pyannote element
pyannote = pipeline.get_by_name('diarization')

# Setup signal callbacks
from gst_pyannote.signaling import SignalManager

signals = SignalManager(element=pyannote)

def on_speaker_detected(speaker, start, end):
    print(f"🗣️  {speaker}: {start:.1f}s - {end:.1f}s")

def on_inference_complete(results):
    speakers = results.get('speakers', [])
    print(f"📊 Currently {len(speakers)} active speakers")

signals.register_callback('speaker-detected', on_speaker_detected)
signals.register_callback('inference-complete', on_inference_complete)

# Run
print("Listening to microphone... Press Ctrl+C to stop")
pipeline.set_state(Gst.State.PLAYING)

loop = GLib.MainLoop()
try:
    loop.run()
except KeyboardInterrupt:
    print("\nStopped")
finally:
    pipeline.set_state(Gst.State.NULL)
```

---

## WebRTC Integration

### Basic WebRTC Pipeline

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

pipeline = Gst.parse_launch("""
    webrtcbin name=webrtc latency=20 !
    queue max-size-buffers=10 !
    rtpopusdepay !
    opusdec !
    audioconvert !
    audioresample !
    audio/x-raw,format=F32LE,rate=16000,channels=1 !
    pyannote
        model-name=pyannote/speaker-diarization-3.1
        low-latency=true
        window-duration=10.0
        overlap-duration=2.0 !
    fakesink dump=true
""")

# Setup WebRTC (offer/answer, ICE, etc.)
webrtc = pipeline.get_by_name('webrtc')

# ... WebRTC setup code ...

pipeline.set_state(Gst.State.PLAYING)

loop = GLib.MainLoop()
loop.run()
```

### With Statistics Monitoring

```python
from gst_pyannote.webrtc_handler import WebRTCHandler
import threading

# Create WebRTC handler
webrtc_handler = WebRTCHandler(low_latency=True)

# Monitor statistics
def print_stats():
    stats = webrtc_handler.get_statistics()
    print(f"""
    WebRTC Statistics:
    - Packets: {stats['packets_received']}
    - Lost: {stats['total_lost']} ({stats['loss_rate']:.1%})
    - Jitter: {stats['jitter']*1000:.1f}ms
    """)

    # Schedule next print
    threading.Timer(10.0, print_stats).start()

print_stats()
```

---

## Control Interface

### Dynamic Model Loading

```python
from gst_pyannote.control_interface import ControlHandler, ControlMessageParser
from gst_pyannote.pipeline_manager import PyannotePipelineManager
from gst_pyannote.inference_worker import InferenceWorker

# Create components
manager = PyannotePipelineManager(device='cuda')
worker = InferenceWorker(manager)
worker.start()

# Create control handler
handler = ControlHandler(
    pipeline_manager=manager,
    inference_worker=worker
)

parser = ControlMessageParser()

# Load model
cmd = '{"command": "load_model", "model_name": "pyannote/speaker-diarization-3.1"}'
message = parser.parse(cmd)
response = handler.handle_message(message)
print(f"Status: {response['status']}")

# Update parameters
cmd = '{"command": "set_parameter", "parameters": {"min_speakers": 2, "max_speakers": 10}}'
message = parser.parse(cmd)
response = handler.handle_message(message)

# Get state
cmd = '{"command": "get_state"}'
message = parser.parse(cmd)
response = handler.handle_message(message)
print(f"State: {response['state']}")

# Pause inference
cmd = '{"command": "pause_inference"}'
message = parser.parse(cmd)
response = handler.handle_message(message)

# Resume
cmd = '{"command": "resume_inference"}'
message = parser.parse(cmd)
response = handler.handle_message(message)

# Cleanup
worker.stop()
```

### Via GStreamer Events

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import json

Gst.init(None)

# Get control pad
pyannote = pipeline.get_by_name('pyannote')
control_pad = pyannote.get_static_pad('control_sink')

# Create control message
message = {
    'command': 'set_parameter',
    'parameters': {
        'min_speakers': 3,
        'max_speakers': 8
    }
}

# Create event
json_str = json.dumps(message)
structure = Gst.Structure.new_from_string(
    f'pyannote-control, message=(string){json_str}'
)
event = Gst.Event.new_custom(Gst.EventType.CUSTOM_DOWNSTREAM, structure)

# Send event
control_pad.send_event(event)
```

---

## Signal Handling

### Python Callbacks

```python
from gst_pyannote.signaling import SignalManager

signals = SignalManager(element=pyannote)

# Model lifecycle
signals.register_callback('model-loaded',
    lambda model: print(f"✅ Model loaded: {model}"))

signals.register_callback('model-unloaded',
    lambda: print("❌ Model unloaded"))

# Inference
signals.register_callback('inference-started',
    lambda timestamp: print(f"⏱️  Inference started at {timestamp:.1f}s"))

signals.register_callback('inference-complete',
    lambda results: print(f"✅ Inference complete: {len(results['events'])} events"))

# Speakers
def on_speaker_detected(speaker_id, start, end):
    duration = end - start
    print(f"🗣️  {speaker_id}: {start:.1f}s - {end:.1f}s ({duration:.1f}s)")

signals.register_callback('speaker-detected', on_speaker_detected)

# Parameters
def on_parameter_changed(param, old, new):
    print(f"⚙️  {param}: {old} → {new}")

signals.register_callback('parameter-changed', on_parameter_changed)

# Errors
signals.register_callback('error-occurred',
    lambda msg, type: print(f"❌ Error ({type}): {msg}"))
```

### GStreamer Bus Messages

```python
def on_bus_message(bus, message):
    if message.type == Gst.MessageType.ELEMENT:
        structure = message.get_structure()
        name = structure.get_name()

        if name == 'pyannote-model-loaded':
            model = structure.get_string('model_name')
            print(f"Model loaded: {model}")

        elif name == 'pyannote-inference-complete':
            speaker_count = structure.get_int('speaker_count')[1]
            event_count = structure.get_int('event_count')[1]
            print(f"Inference: {speaker_count} speakers, {event_count} events")

        elif name == 'pyannote-parameter-changed':
            param = structure.get_string('parameter')
            new_value = structure.get_string('new_value')
            print(f"Parameter {param} = {new_value}")

bus = pipeline.get_bus()
bus.add_signal_watch()
bus.connect('message', on_bus_message)
```

### Custom Event Probes

```python
def event_probe(pad, info):
    event = info.get_event()

    if event.type == Gst.EventType.CUSTOM_DOWNSTREAM:
        structure = event.get_structure()
        name = structure.get_name()

        if name == 'pyannote-speaker-detected':
            speaker = structure.get_string('speaker')
            start = structure.get_double('start')[1]
            end = structure.get_double('end')[1]

            # Could trigger actions:
            # - Update UI
            # - Record segment
            # - Send notification
            # - Log to database

            print(f"Detected: {speaker} at {start:.1f}s")

    return Gst.PadProbeReturn.OK

# Attach probe to downstream element
downstream_pad = downstream_element.get_static_pad('sink')
downstream_pad.add_probe(
    Gst.PadProbeType.EVENT_DOWNSTREAM,
    event_probe
)
```

---

## Advanced Examples

### Multi-File Batch Processing

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from pathlib import Path
import json

class BatchProcessor:
    def __init__(self, model_name):
        Gst.init(None)
        self.model_name = model_name
        self.current_file = None
        self.results = {}

    def process_file(self, input_file):
        self.current_file = input_file

        # Create pipeline
        self.pipeline = Gst.parse_launch(f"""
            filesrc name=src !
            decodebin !
            audioconvert !
            audioresample !
            pyannote name=diarization model-name={self.model_name} !
            fakesink
        """)

        # Set file
        src = self.pipeline.get_by_name('src')
        src.set_property('location', str(input_file))

        # Setup signals
        pyannote = self.pipeline.get_by_name('diarization')
        from gst_pyannote.signaling import SignalManager

        signals = SignalManager(element=pyannote)
        signals.register_callback('inference-complete', self.on_result)

        # Handle bus
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

        # Run
        print(f"Processing {input_file.name}...")
        self.pipeline.set_state(Gst.State.PLAYING)

        self.loop = GLib.MainLoop()
        self.loop.run()

        self.pipeline.set_state(Gst.State.NULL)

    def on_result(self, results):
        # Store results
        if self.current_file not in self.results:
            self.results[self.current_file] = []

        self.results[self.current_file].append(results)

    def on_message(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}")
            self.loop.quit()
        elif message.type == Gst.MessageType.EOS:
            self.loop.quit()

    def save_results(self, output_file):
        # Convert Path keys to strings for JSON
        json_results = {
            str(k): v for k, v in self.results.items()
        }

        with open(output_file, 'w') as f:
            json.dump(json_results, f, indent=2)

        print(f"Saved results to {output_file}")

# Usage
processor = BatchProcessor('pyannote/speaker-diarization-3.1')

audio_dir = Path('audio_files')
for audio_file in audio_dir.glob('*.wav'):
    processor.process_file(audio_file)

processor.save_results('batch_results.json')
```

### Real-Time Dashboard

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from collections import defaultdict
import time

class RealtimeDashboard:
    def __init__(self):
        self.speaker_times = defaultdict(float)
        self.total_speech = 0.0
        self.last_update = time.time()

    def on_speaker_detected(self, speaker, start, end):
        duration = end - start
        self.speaker_times[speaker] += duration
        self.total_speech += duration

        # Update dashboard every second
        now = time.time()
        if now - self.last_update >= 1.0:
            self.print_dashboard()
            self.last_update = now

    def print_dashboard(self):
        print("\033[2J\033[H")  # Clear screen
        print("=" * 60)
        print("Real-Time Speaker Diarization Dashboard")
        print("=" * 60)
        print()

        # Sort speakers by total time
        sorted_speakers = sorted(
            self.speaker_times.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for speaker, duration in sorted_speakers:
            percentage = (duration / self.total_speech * 100) if self.total_speech > 0 else 0
            bar_length = int(percentage / 2)
            bar = "█" * bar_length

            print(f"{speaker:12s} {duration:6.1f}s [{bar:<50s}] {percentage:5.1f}%")

        print()
        print(f"Total speech time: {self.total_speech:.1f}s")
        print()
        print("Press Ctrl+C to stop")

# Setup pipeline with dashboard
Gst.init(None)

pipeline = Gst.parse_launch("""
    pulsesrc !
    audioconvert !
    audioresample !
    pyannote name=diarization
        model-name=pyannote/speaker-diarization-3.1
        low-latency=true !
    fakesink
""")

pyannote = pipeline.get_by_name('diarization')

from gst_pyannote.signaling import SignalManager
dashboard = RealtimeDashboard()

signals = SignalManager(element=pyannote)
signals.register_callback('speaker-detected', dashboard.on_speaker_detected)

pipeline.set_state(Gst.State.PLAYING)

loop = GLib.MainLoop()
try:
    loop.run()
except KeyboardInterrupt:
    dashboard.print_dashboard()
    print("\nStopped")
finally:
    pipeline.set_state(Gst.State.NULL)
```

### Custom JSON Processing

```python
#!/usr/bin/env python3
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import json
import sqlite3

class DiarizationDatabase:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY,
                speaker TEXT,
                start_time REAL,
                end_time REAL,
                duration REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def store_segment(self, speaker, start, end):
        duration = end - start
        self.conn.execute("""
            INSERT INTO segments (speaker, start_time, end_time, duration)
            VALUES (?, ?, ?, ?)
        """, (speaker, start, end, duration))
        self.conn.commit()

    def get_speaker_stats(self):
        cursor = self.conn.execute("""
            SELECT speaker,
                   COUNT(*) as segment_count,
                   SUM(duration) as total_time,
                   AVG(duration) as avg_duration
            FROM segments
            GROUP BY speaker
            ORDER BY total_time DESC
        """)
        return cursor.fetchall()

# Setup
Gst.init(None)
db = DiarizationDatabase('diarization.db')

pipeline = Gst.parse_launch("""
    filesrc location=meeting.wav !
    decodebin !
    audioconvert !
    pyannote name=diarization !
    fakesink
""")

# Connect to signals
pyannote = pipeline.get_by_name('diarization')
from gst_pyannote.signaling import SignalManager

signals = SignalManager(element=pyannote)
signals.register_callback('speaker-detected',
    lambda speaker, start, end: db.store_segment(speaker, start, end))

# Run pipeline
pipeline.set_state(Gst.State.PLAYING)

bus = pipeline.get_bus()
msg = bus.timed_pop_filtered(
    Gst.CLOCK_TIME_NONE,
    Gst.MessageType.ERROR | Gst.MessageType.EOS
)

pipeline.set_state(Gst.State.NULL)

# Print statistics
print("\nSpeaker Statistics:")
print("-" * 60)
for speaker, count, total, avg in db.get_speaker_stats():
    print(f"{speaker}: {count} segments, {total:.1f}s total, {avg:.1f}s avg")
```

---

## Troubleshooting

### Model Loading Issues

**Problem:** Model fails to load

```python
# Check if auth token is needed
from gst_pyannote.control_interface import ControlHandler

handler = ControlHandler(pipeline_manager=manager)

response = handler.handle_message({
    'command': 'load_model',
    'model_name': 'pyannote/speaker-diarization-3.1',
    'auth_token': 'hf_your_token_here'  # Get from huggingface.co
})

if response['status'] == 'error':
    print(f"Error: {response['message']}")
```

### Memory Issues

**Problem:** Out of memory errors

```python
# Use smaller windows
pyannote.set_property('window-duration', 15.0)  # Instead of 30.0

# Use CPU instead of GPU (uses less memory)
pyannote.set_property('device', 'cpu')

# Reduce inference queue size
worker = InferenceWorker(manager, max_queue_size=3)  # Instead of 10
```

### Latency Too High

**Problem:** Too much delay in real-time processing

```python
# Enable low-latency mode
pyannote.set_property('low-latency', True)

# Reduce window size
pyannote.set_property('window-duration', 10.0)
pyannote.set_property('overlap-duration', 2.0)

# Use GPU
pyannote.set_property('device', 'cuda')
```

### No Output

**Problem:** No JSON output on json_src pad

```python
# Check if inference is enabled
pyannote.set_property('inference-enabled', True)

# Check if model is loaded
from gst_pyannote.control_interface import ControlHandler

response = handler.handle_message({'command': 'get_state'})
print(f"Model loaded: {response['state']['pipeline_loaded']}")

# Check for errors on bus
def on_message(bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}\nDebug: {debug}")

bus.connect('message', on_message)
```

### Packet Loss (WebRTC)

**Problem:** High packet loss in WebRTC streams

```python
from gst_pyannote.webrtc_handler import WebRTCHandler

handler = WebRTCHandler()

# Enable packet loss concealment
handler.enable_plc(True)

# Increase jitter buffer
handler.set_jitter_latency(100)  # 100ms

# Monitor statistics
stats = handler.get_statistics()
if stats['loss_rate'] > 0.05:  # >5% loss
    print(f"Warning: High packet loss ({stats['loss_rate']:.1%})")
```

### Debug Logging

Enable detailed logging:

```bash
# GStreamer debug
export GST_DEBUG=pyannote:5,python:4

# Python logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run application
python my_app.py
```

---

## Performance Tips

1. **Use GPU for real-time processing**
   ```python
   pyannote.set_property('device', 'cuda')
   ```

2. **Optimize window size for your use case**
   - Accuracy: Larger windows (30s)
   - Latency: Smaller windows (10s)

3. **Monitor resource usage**
   ```python
   stats = handler.get_statistics()
   queue_size = worker.get_queue_size()
   ```

4. **Use low-latency mode for real-time**
   ```python
   pyannote.set_property('low-latency', True)
   ```

5. **Batch process files when possible**
   - More efficient than real-time for offline files

---

## Next Steps

- See [API.md](API.md) for complete API reference
- See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment
- See [BEST_PRACTICES.md](BEST_PRACTICES.md) for optimization tips
- Check [examples/](../examples/) for more code samples
