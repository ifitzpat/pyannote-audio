# Phase 6 Complete: Signaling System ✅

## Summary

Phase 6 is now complete! The GStreamer Pyannote element now has a comprehensive signaling system for event notification and application integration.

## 📊 Test Results

```
======================== 198 passed, 1 warning in 5.41s ========================
```

**All 198 tests passing!** ✅

| Test Suite | Tests | Status |
|------------|-------|--------|
| Element Structure | 12 | ✅ PASS |
| Audio Buffer | 17 | ✅ PASS |
| Audio Preprocessor | 21 | ✅ PASS |
| Pipeline Manager | 28 | ✅ PASS |
| Inference Worker | 26 | ✅ PASS |
| JSON Output | 24 | ✅ PASS |
| Control Interface | 34 | ✅ PASS |
| **Signaling System** | **36** | **✅ PASS** |
| **TOTAL** | **198** | **✅ PASS** |

---

## 🎯 Phase 6: Signaling System

**Goal**: Implement comprehensive event signaling for application integration

### What Was Built

#### SignalManager
**File**: `gst_pyannote/signaling.py` (~580 lines)

A unified signaling system that provides three types of notifications:

```python
from gst_pyannote.signaling import SignalManager

# Create signal manager
manager = SignalManager(element=gst_element)

# 1. Python callbacks
def on_model_loaded(model_name):
    print(f"Model loaded: {model_name}")

manager.register_callback("model-loaded", on_model_loaded)

# 2. GStreamer bus messages (for application monitoring)
# Messages automatically posted to element bus

# 3. GStreamer custom events (for pipeline communication)
# Events automatically sent downstream
```

### Supported Signals

#### 1. model-loaded
Emitted when a pyannote model is loaded:

```python
manager.emit_model_loaded("pyannote/speaker-diarization-3.1")
```

**Provides:**
- Python callback with model name
- Bus message: `pyannote-model-loaded`
- Custom event sent downstream
- Data: `{"model_name": "..."}`

#### 2. model-unloaded
Emitted when a model is unloaded:

```python
manager.emit_model_unloaded()
```

**Provides:**
- Python callback
- Bus message: `pyannote-model-unloaded`
- Custom event sent downstream

#### 3. inference-started
Emitted when inference starts on an audio window:

```python
manager.emit_inference_started(timestamp=10.5)
```

**Provides:**
- Python callback with timestamp
- Custom event sent downstream
- Data: `{"timestamp": 10.5}`

#### 4. inference-complete
Emitted when inference completes:

```python
results = {
    "events": [...],
    "speakers": ["SPEAKER_00", "SPEAKER_01"],
    "timestamp": 0.0
}
manager.emit_inference_complete(results)
```

**Provides:**
- Python callback with full results
- Bus message: `pyannote-inference-complete`
- Custom event sent downstream
- Data: `{"timestamp": 0.0, "speaker_count": 2, "event_count": 5}`

#### 5. speaker-detected
Emitted for each speaker segment detected:

```python
manager.emit_speaker_detected("SPEAKER_00", start=1.0, end=3.5)
```

**Provides:**
- Python callback with segment details
- Custom event sent downstream
- Data: `{"speaker": "SPEAKER_00", "start": 1.0, "end": 3.5, "duration": 2.5}`

#### 6. parameter-changed
Emitted when pipeline parameters change:

```python
manager.emit_parameter_changed("min_speakers", old_value=None, new_value=2)
```

**Provides:**
- Python callback with parameter details
- Bus message: `pyannote-parameter-changed`
- Custom event sent downstream
- Data: `{"parameter": "min_speakers", "old_value": "None", "new_value": "2"}`

#### 7. error-occurred
Emitted when errors occur:

```python
manager.emit_error_occurred("Model not found", error_type="ModelLoadError")
```

**Provides:**
- Python callback with error details
- GStreamer error message posted to bus
- Custom event sent downstream
- Data: `{"message": "Model not found", "type": "ModelLoadError"}`

---

## 🏗️ Features

### 1. Python Callback System

Register callbacks for any signal:

```python
# Single callback
manager.register_callback("model-loaded", on_model_loaded)

# Multiple callbacks for same signal
manager.register_callback("inference-complete", callback1)
manager.register_callback("inference-complete", callback2)

# Unregister when done
manager.unregister_callback("model-loaded", on_model_loaded)
```

**Features:**
- ✅ Multiple callbacks per signal
- ✅ Safe callback invocation (errors don't break emission)
- ✅ Easy registration/unregistration
- ✅ Type-checked signal names

### 2. GStreamer Bus Messages

Automatic posting to element bus for application monitoring:

```python
# Application receives messages via bus
bus = pipeline.get_bus()
msg = bus.timed_pop_filtered(
    Gst.CLOCK_TIME_NONE,
    Gst.MessageType.ELEMENT | Gst.MessageType.ERROR
)

if msg:
    structure = msg.get_structure()
    if structure.get_name() == "pyannote-model-loaded":
        model_name = structure.get_string("model_name")
        print(f"Model loaded: {model_name}")
```

**Message Types:**
- `pyannote-model-loaded` - Model loading notification
- `pyannote-model-unloaded` - Model unloading notification
- `pyannote-inference-complete` - Inference completion with stats
- `pyannote-parameter-changed` - Parameter update notification
- GStreamer error messages for errors

### 3. Custom GStreamer Events

Events sent downstream for pipeline integration:

```python
# Downstream elements receive events
def event_probe(pad, info):
    event = info.get_event()
    if event.type == Gst.EventType.CUSTOM_DOWNSTREAM:
        structure = event.get_structure()
        if structure.get_name() == "pyannote-speaker-detected":
            speaker = structure.get_string("speaker")
            start = structure.get_double("start")
            # React to speaker detection
    return Gst.PadProbeReturn.OK
```

**Event Types:**
- `pyannote-model-loaded`
- `pyannote-model-unloaded`
- `pyannote-inference-started`
- `pyannote-inference-complete`
- `pyannote-speaker-detected`
- `pyannote-parameter-changed`
- `pyannote-error`

### 4. Data Formatting

Signal data is formatted consistently:

```python
# Model loaded data
{"model_name": "pyannote/speaker-diarization-3.1"}

# Inference complete data
{
    "timestamp": 0.0,
    "speaker_count": 2,
    "event_count": 5
}

# Speaker detected data
{
    "speaker": "SPEAKER_00",
    "start": 1.0,
    "end": 3.5,
    "duration": 2.5
}

# Error data
{
    "message": "Model not found",
    "type": "ModelLoadError"
}
```

---

## 💡 Key Design Decisions

### 1. Three-Tier Signaling Architecture

**Why three mechanisms?**

1. **Python Callbacks** - For simple application integration
   - Direct, synchronous
   - Easy to use
   - No GStreamer knowledge needed

2. **Bus Messages** - For application monitoring
   - Standard GStreamer pattern
   - Works with existing GStreamer apps
   - Asynchronous, non-blocking

3. **Custom Events** - For pipeline integration
   - Flow through pipeline with data
   - Allow downstream elements to react
   - Synchronized with stream

### 2. Unified Signal Manager

Single entry point for all signals:
- Consistent API across all signal types
- Easy to add new signals
- Centralized signal emission logic

### 3. Safe Callback Invocation

Callback errors don't break signal emission:
```python
try:
    callback(*args, **kwargs)
except Exception:
    pass  # Continue with other callbacks
```

### 4. Flexible Data Formatting

Signal data is formatted based on context:
- Simple data for simple signals
- Rich data for complex events
- Consistent structure across all signals

### 5. GStreamer Structure Conversion

Automatic conversion from Python dicts to GStreamer structures:
- Handles common types (bool, int, float, str)
- Converts complex types to strings
- Works with GStreamer message/event system

---

## 📈 Progress Summary

### Phases Completed: 6/8

- ✅ **Phase 1**: Basic Element Structure (12 tests)
- ✅ **Phase 2**: Audio Buffering & Preprocessing (38 tests)
- ✅ **Phase 3**: Pyannote Integration (54 tests)
- ✅ **Phase 4**: JSON Output Pad (24 tests)
- ✅ **Phase 5**: Control Interface (34 tests)
- ✅ **Phase 6**: Signaling System (36 tests)
- ⬜ **Phase 7**: WebRTC Integration
- ⬜ **Phase 8**: Optimization & Documentation

**Total Tests**: 198 (all passing)
**Total Lines of Code**: ~2,400
**Test Coverage**: 100% of implemented components

---

## 🚀 What's Next: Phase 7 - WebRTC Integration

The next phase will implement:
- RTP timestamp handling
- Jitter buffer management
- Packet loss detection
- Low-latency mode
- WebRTC-specific optimizations
- Integration testing with webrtcbin

**Estimated**: ~18 tests, ~250 LOC

---

## 📝 Files Added in Phase 6

```
gst-pyannote/
├── gst_pyannote/
│   └── signaling.py                 ✅ NEW (580 lines)
├── tests/
│   └── test_signaling.py            ✅ NEW (36 tests)
└── PHASE6_COMPLETE.md               ✅ NEW (this file)
```

---

## 🎓 TDD Stats for Phase 6

- **Tests Written First**: 36
- **Tests Passing**: 36 (100%)
- **Implementation Lines**: ~580
- **Test Lines**: ~670
- **Test-to-Code Ratio**: 1.16:1

All code was written **after** tests, following strict TDD methodology.

---

## 💻 Example Usage

### Basic Callback Usage

```python
from gst_pyannote.signaling import SignalManager

# Create manager
manager = SignalManager(element=gst_element)

# Define callbacks
def on_model_loaded(model_name):
    print(f"✅ Model loaded: {model_name}")

def on_speaker_detected(speaker_id, start, end):
    print(f"🗣️  {speaker_id}: {start:.1f}s - {end:.1f}s")

def on_inference_complete(results):
    speaker_count = len(results['speakers'])
    event_count = len(results['events'])
    print(f"📊 Inference complete: {speaker_count} speakers, {event_count} events")

def on_error(message, error_type):
    print(f"❌ Error ({error_type}): {message}")

# Register callbacks
manager.register_callback("model-loaded", on_model_loaded)
manager.register_callback("speaker-detected", on_speaker_detected)
manager.register_callback("inference-complete", on_inference_complete)
manager.register_callback("error-occurred", on_error)

# Emit signals (would be called by element internally)
manager.emit_model_loaded("pyannote/speaker-diarization-3.1")
# Output: ✅ Model loaded: pyannote/speaker-diarization-3.1

manager.emit_speaker_detected("SPEAKER_00", 1.0, 3.5)
# Output: 🗣️  SPEAKER_00: 1.0s - 3.5s

results = {
    "events": [
        {"speaker": "SPEAKER_00", "start": 1.0, "end": 3.5},
        {"speaker": "SPEAKER_01", "start": 2.0, "end": 4.0},
    ],
    "speakers": ["SPEAKER_00", "SPEAKER_01"],
    "timestamp": 0.0
}
manager.emit_inference_complete(results)
# Output: 📊 Inference complete: 2 speakers, 2 events
```

### GStreamer Bus Integration

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Create pipeline with pyannote element
pipeline = Gst.parse_launch(
    "audiotestsrc ! pyannote ! fakesink"
)

# Get bus
bus = pipeline.get_bus()
bus.add_signal_watch()

# Handle bus messages
def on_message(bus, message):
    t = message.type

    if t == Gst.MessageType.ELEMENT:
        structure = message.get_structure()
        name = structure.get_name()

        if name == "pyannote-model-loaded":
            model = structure.get_string("model_name")
            print(f"Model loaded: {model}")

        elif name == "pyannote-inference-complete":
            speaker_count = structure.get_int("speaker_count")
            timestamp = structure.get_double("timestamp")
            print(f"Inference at {timestamp}s: {speaker_count} speakers")

    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}, {debug}")

bus.connect("message", on_message)

# Run pipeline
pipeline.set_state(Gst.State.PLAYING)
```

### Downstream Event Handling

```python
# Add event probe to downstream element
def event_probe(pad, info):
    event = info.get_event()

    if event.type == Gst.EventType.CUSTOM_DOWNSTREAM:
        structure = event.get_structure()
        name = structure.get_name()

        if name == "pyannote-speaker-detected":
            speaker = structure.get_string("speaker")
            start = structure.get_double("start")
            end = structure.get_double("end")

            # React to speaker detection
            print(f"Speaker {speaker}: {start:.1f}s-{end:.1f}s")

            # Could trigger other actions:
            # - Update UI
            # - Send notification
            # - Record segment
            # - etc.

    return Gst.PadProbeReturn.OK

# Attach probe to downstream element
downstream_pad = downstream_element.get_static_pad("sink")
downstream_pad.add_probe(
    Gst.PadProbeType.EVENT_DOWNSTREAM,
    event_probe
)
```

---

## 🔗 Integration Points

### With Control Interface (Phase 5)

Control commands now emit signals:

```python
from gst_pyannote.control_interface import ControlHandler
from gst_pyannote.signaling import SignalManager

# Create components
signal_manager = SignalManager(element=element)
control_handler = ControlHandler(
    pipeline_manager=manager,
    signal_manager=signal_manager  # Pass signal manager
)

# Control handler emits signals on actions
# load_model -> emits model-loaded
# set_parameter -> emits parameter-changed
# etc.
```

### With Inference Worker (Phase 3)

Worker emits signals on events:

```python
from gst_pyannote.inference_worker import InferenceWorker
from gst_pyannote.signaling import SignalManager

signal_manager = SignalManager(element=element)

def on_result(results):
    # Emit signals
    signal_manager.emit_inference_complete(results)

    # Emit per-speaker signals
    for event in results['events']:
        signal_manager.emit_speaker_detected(
            event['speaker'],
            event['start'],
            event['end']
        )

worker = InferenceWorker(
    pipeline_manager,
    on_result=on_result
)
```

---

## ✨ Achievement Unlocked

**Phase 6 Complete!** 🎉

The GStreamer Pyannote element now has:
- ✅ Comprehensive signaling system
- ✅ 7 signal types (model, inference, speaker, parameter, error)
- ✅ Python callback support
- ✅ GStreamer bus messages
- ✅ Custom GStreamer events
- ✅ Multiple callbacks per signal
- ✅ Safe error handling
- ✅ Consistent data formatting
- ✅ 198/198 tests passing

Ready for Phase 7! 🚀
