# GStreamer Pyannote API Documentation

Complete API reference for the GStreamer Pyannote speaker diarization element.

## Table of Contents

- [GStreamer Element](#gstreamer-element)
- [Python API](#python-api)
  - [Audio Processing](#audio-processing)
  - [Pipeline Management](#pipeline-management)
  - [Control Interface](#control-interface)
  - [Signaling System](#signaling-system)
  - [WebRTC Handler](#webrtc-handler)
- [Properties](#properties)
- [Signals](#signals)
- [Events](#events)
- [Bus Messages](#bus-messages)

---

## GStreamer Element

### Element Name

`pyannote`

### Classification

Filter/Audio/Analysis

### Description

Real-time speaker diarization using pyannote-audio models.

### Pads

#### Sink Pad (audio_sink)

Accepts raw audio input.

**Capabilities:**
```
audio/x-raw,
  format=(string)F32LE,
  rate=(int){8000,16000,22050,32000,44100,48000},
  channels=(int)[1,2],
  layout=(string)interleaved
```

**Notes:**
- Automatically converts to mono if stereo
- Automatically resamples to 16kHz for pyannote
- Supports common sample rates

#### Source Pad (audio_src)

Outputs audio (passthrough when inference disabled).

**Capabilities:**
```
audio/x-raw,
  format=(string)F32LE,
  rate=(int)[8000,96000],
  channels=(int)[1,8],
  layout=(string)interleaved
```

#### JSON Source Pad (json_src)

Outputs diarization results as JSON.

**Capabilities:**
```
application/json
```

**JSON Format:**
```json
{
  "type": "diarization",
  "timestamp": 0.0,
  "events": [
    {
      "speaker": "SPEAKER_00",
      "start": 1.2,
      "end": 3.5
    }
  ],
  "speakers": ["SPEAKER_00", "SPEAKER_01"]
}
```

#### Control Sink Pad (control_sink)

Accepts control messages as JSON.

**Capabilities:**
```
application/json
```

**Control Message Format:**
```json
{
  "command": "load_model",
  "model_name": "pyannote/speaker-diarization-3.1",
  "request_id": "optional-id"
}
```

---

## Properties

### model-name

**Type:** `string`
**Default:** `None`
**Description:** Name of the pyannote model to load
**Example:** `"pyannote/speaker-diarization-3.1"`

### min-speakers

**Type:** `int`
**Range:** 1-100
**Default:** `None` (auto-detect)
**Description:** Minimum number of speakers to detect

### max-speakers

**Type:** `int`
**Range:** 1-100
**Default:** `None` (auto-detect)
**Description:** Maximum number of speakers to detect

### window-duration

**Type:** `float`
**Range:** 1.0-60.0
**Default:** 30.0
**Unit:** seconds
**Description:** Duration of sliding window for diarization

### overlap-duration

**Type:** `float`
**Range:** 0.0-30.0
**Default:** 5.0
**Unit:** seconds
**Description:** Overlap between consecutive windows

### inference-enabled

**Type:** `bool`
**Default:** `True`
**Description:** Enable/disable inference processing

### device

**Type:** `string`
**Default:** `"auto"`
**Options:** `"auto"`, `"cpu"`, `"cuda"`, `"cuda:0"`, etc.
**Description:** Device for inference (CPU or GPU)

### low-latency

**Type:** `bool`
**Default:** `False`
**Description:** Enable low-latency mode for real-time processing

---

## Python API

### Audio Processing

#### AudioRingBuffer

Manages sliding window audio accumulation.

```python
from gst_pyannote.audio_buffer import AudioRingBuffer

buffer = AudioRingBuffer(
    window_duration=30.0,
    overlap_duration=5.0,
    sample_rate=16000
)

# Push audio chunk
result = buffer.push(audio_tensor)

# Result is (audio_window, start_time, end_time) when ready
if result:
    audio, start, end = result
    # Process window
```

**Methods:**

- `push(audio_chunk: torch.Tensor) -> Optional[Tuple]`
  - Add audio to buffer
  - Returns window when ready

- `reset() -> None`
  - Clear buffer and reset timestamps

- `is_ready() -> bool`
  - Check if buffer has enough samples

- `get_duration() -> float`
  - Get current buffer duration in seconds

#### AudioPreprocessor

Converts GStreamer buffers to PyTorch tensors.

```python
from gst_pyannote.audio_preprocessor import AudioPreprocessor

preprocessor = AudioPreprocessor(target_rate=16000)

# Process audio
audio_tensor = preprocessor.process(
    audio_np,
    source_rate=48000,
    channels=2,
    format_str='F32LE',
    to_mono=True
)
```

**Methods:**

- `process(audio_np, source_rate, channels, format_str, to_mono=True) -> torch.Tensor`
  - Convert and preprocess audio
  - Returns mono F32 tensor at target rate

- `numpy_to_tensor(audio_np, channels, format_str) -> torch.Tensor`
  - Convert numpy to tensor

- `stereo_to_mono(audio) -> torch.Tensor`
  - Downmix stereo to mono

- `resample(audio, source_rate) -> torch.Tensor`
  - Resample audio to target rate

---

### Pipeline Management

#### PyannotePipelineManager

Manages pyannote pipeline lifecycle.

```python
from gst_pyannote.pipeline_manager import PyannotePipelineManager

manager = PyannotePipelineManager(device='cuda')

# Load model
manager.load_pipeline(
    'pyannote/speaker-diarization-3.1',
    use_auth_token='hf_...'
)

# Process audio
results = manager.process_audio(
    audio_tensor,
    sample_rate=16000,
    start_time=0.0
)

# Update parameters
manager.update_parameters({
    'min_speakers': 2,
    'max_speakers': 10
})

# Unload model
manager.unload_pipeline()
```

**Methods:**

- `load_pipeline(model_name, use_auth_token=None)`
  - Load pyannote model

- `unload_pipeline()`
  - Unload model and free resources

- `is_loaded() -> bool`
  - Check if model is loaded

- `process_audio(audio_tensor, sample_rate, start_time) -> dict`
  - Run diarization on audio window

- `update_parameters(params: dict)`
  - Update pipeline parameters

- `get_parameters() -> dict`
  - Get current parameters

#### InferenceWorker

Background thread for async inference.

```python
from gst_pyannote.inference_worker import InferenceWorker

worker = InferenceWorker(
    pipeline_manager,
    max_queue_size=10,
    on_result=result_callback,
    on_error=error_callback
)

# Start worker
worker.start()

# Submit audio for inference
worker.submit_audio(
    audio_tensor,
    sample_rate=16000,
    start_time=0.0,
    block=True
)

# Stop worker
worker.stop()

# Get queue size
size = worker.get_queue_size()

# Clear queue
worker.clear_queue()
```

**Methods:**

- `start()`
  - Start background worker thread

- `stop()`
  - Stop worker and wait for completion

- `submit_audio(audio_tensor, sample_rate, start_time, block=True, timeout=None)`
  - Submit audio for inference

- `get_queue_size() -> int`
  - Get current queue size

- `clear_queue()`
  - Clear pending items

---

### Control Interface

#### ControlMessageParser

Parse JSON control messages.

```python
from gst_pyannote.control_interface import ControlMessageParser

parser = ControlMessageParser()

message = parser.parse('{"command": "load_model", "model_name": "..."}')
```

**Methods:**

- `parse(json_str: str) -> Optional[dict]`
  - Parse JSON control message
  - Returns parsed dict or error dict

#### ControlHandler

Execute control commands.

```python
from gst_pyannote.control_interface import ControlHandler

handler = ControlHandler(
    element=gst_element,
    pipeline_manager=manager,
    inference_worker=worker
)

response = handler.handle_message({
    'command': 'load_model',
    'model_name': 'pyannote/speaker-diarization-3.1'
})
```

**Supported Commands:**

1. **load_model**
   ```json
   {
     "command": "load_model",
     "model_name": "pyannote/speaker-diarization-3.1",
     "auth_token": "hf_..."
   }
   ```

2. **unload_model**
   ```json
   {
     "command": "unload_model"
   }
   ```

3. **set_parameter**
   ```json
   {
     "command": "set_parameter",
     "parameters": {
       "min_speakers": 2,
       "max_speakers": 10
     }
   }
   ```

4. **get_state**
   ```json
   {
     "command": "get_state"
   }
   ```

5. **pause_inference**
   ```json
   {
     "command": "pause_inference"
   }
   ```

6. **resume_inference**
   ```json
   {
     "command": "resume_inference"
   }
   ```

7. **reset**
   ```json
   {
     "command": "reset"
   }
   ```

**Response Format:**
```json
{
  "status": "success",
  "command": "load_model",
  "request_id": "optional-id",
  "timestamp": 1234567890.123
}
```

---

### Signaling System

#### SignalManager

Manage signal emission.

```python
from gst_pyannote.signaling import SignalManager

manager = SignalManager(element=gst_element)

# Register callback
def on_speaker_detected(speaker_id, start, end):
    print(f"Speaker {speaker_id}: {start:.1f}s-{end:.1f}s")

manager.register_callback('speaker-detected', on_speaker_detected)

# Emit signal
manager.emit_speaker_detected('SPEAKER_00', 1.0, 3.5)

# Unregister callback
manager.unregister_callback('speaker-detected', on_speaker_detected)
```

**Available Signals:**

1. **model-loaded** - `(model_name: str)`
2. **model-unloaded** - `()`
3. **inference-started** - `(timestamp: float)`
4. **inference-complete** - `(results: dict)`
5. **speaker-detected** - `(speaker_id: str, start: float, end: float)`
6. **parameter-changed** - `(parameter: str, old_value, new_value)`
7. **error-occurred** - `(message: str, error_type: str)`

**Methods:**

- `register_callback(signal_name, callback)`
  - Register callback for signal

- `unregister_callback(signal_name, callback)`
  - Unregister callback

- `emit_model_loaded(model_name)`
- `emit_model_unloaded()`
- `emit_inference_started(timestamp)`
- `emit_inference_complete(results)`
- `emit_speaker_detected(speaker_id, start, end)`
- `emit_parameter_changed(parameter, old_value, new_value)`
- `emit_error_occurred(message, error_type)`

---

### WebRTC Handler

#### WebRTCHandler

Handle WebRTC-specific features.

```python
from gst_pyannote.webrtc_handler import WebRTCHandler

handler = WebRTCHandler(
    element=gst_element,
    low_latency=True
)

# Configure from caps
handler.configure_from_caps('application/x-rtp,clock-rate=48000')

# Process RTP buffer
result = handler.process_buffer(buffer, sample_rate=48000)

# Get statistics
stats = handler.get_statistics()
```

**Methods:**

- `convert_rtp_to_pts(rtp_timestamp, sample_rate) -> int`
  - Convert RTP timestamp to PTS (nanoseconds)

- `set_rtp_base(rtp_timestamp, sample_rate)`
  - Set base RTP timestamp for relative conversion

- `process_buffer(buffer, sample_rate) -> dict`
  - Process buffer with RTP metadata

- `extract_ssrc(buffer) -> Optional[int]`
- `extract_payload_type(buffer) -> Optional[int]`
- `extract_rtp_timestamp(buffer) -> Optional[int]`
- `extract_sequence_number(buffer) -> Optional[int]`

- `get_statistics() -> dict`
  - Get WebRTC statistics

- `configure_from_caps(caps_string)`
  - Configure from GStreamer caps

- `enable_plc(enabled: bool)`
  - Enable packet loss concealment

- `set_jitter_latency(latency_ms: int)`
  - Set jitter buffer latency

#### JitterBuffer

Reorder out-of-order packets.

```python
from gst_pyannote.webrtc_handler import JitterBuffer

buffer = JitterBuffer(max_size=100)

buffer.push({'seq': 102, 'timestamp': 48200, 'data': b'...'})
buffer.push({'seq': 100, 'timestamp': 48000, 'data': b'...'})
buffer.push({'seq': 101, 'timestamp': 48100, 'data': b'...'})

packet = buffer.pop()  # Returns seq 100
```

**Methods:**

- `push(packet: dict)`
  - Add packet to buffer

- `pop() -> Optional[dict]`
  - Remove and return next packet in sequence

- `size() -> int`
  - Get current buffer size

- `clear()`
  - Clear buffer

#### PacketLossDetector

Detect packet loss.

```python
from gst_pyannote.webrtc_handler import PacketLossDetector

detector = PacketLossDetector()

lost = detector.process_packet(100)  # []
lost = detector.process_packet(103)  # [101, 102]

stats = detector.get_statistics()
```

**Methods:**

- `process_packet(sequence: int) -> List[int]`
  - Process packet and detect loss

- `get_statistics() -> dict`
  - Get loss statistics

---

## Bus Messages

The element posts messages to the GStreamer bus for application monitoring.

### Element Messages

#### pyannote-model-loaded

Posted when a model is loaded.

**Structure:**
```
pyannote-model-loaded, model_name=(string)"pyannote/speaker-diarization-3.1"
```

#### pyannote-model-unloaded

Posted when a model is unloaded.

**Structure:**
```
pyannote-model-unloaded
```

#### pyannote-inference-complete

Posted when inference completes on a window.

**Structure:**
```
pyannote-inference-complete,
  timestamp=(double)0.0,
  speaker_count=(int)2,
  event_count=(int)5
```

#### pyannote-parameter-changed

Posted when parameters change.

**Structure:**
```
pyannote-parameter-changed,
  parameter=(string)"min_speakers",
  old_value=(string)"None",
  new_value=(string)"2"
```

### Error Messages

Standard GStreamer error messages are posted for errors:

```python
def on_message(bus, message):
    if message.type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}")
```

---

## Custom Events

The element sends custom downstream events for pipeline communication.

### Event Types

All events have type `Gst.EventType.CUSTOM_DOWNSTREAM`.

#### pyannote-model-loaded

**Structure:**
```
pyannote-model-loaded, model_name=(string)"..."
```

#### pyannote-speaker-detected

**Structure:**
```
pyannote-speaker-detected,
  speaker=(string)"SPEAKER_00",
  start=(double)1.0,
  end=(double)3.5,
  duration=(double)2.5
```

#### pyannote-inference-complete

**Structure:**
```
pyannote-inference-complete,
  timestamp=(double)0.0,
  speaker_count=(int)2,
  event_count=(int)5
```

### Receiving Events

```python
def event_probe(pad, info):
    event = info.get_event()
    if event.type == Gst.EventType.CUSTOM_DOWNSTREAM:
        structure = event.get_structure()
        name = structure.get_name()

        if name == 'pyannote-speaker-detected':
            speaker = structure.get_string('speaker')
            start = structure.get_double('start')
            end = structure.get_double('end')
            print(f"{speaker}: {start:.1f}s-{end:.1f}s")

    return Gst.PadProbeReturn.OK

# Attach probe
pad = element.get_static_pad('sink')
pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, event_probe)
```

---

## Performance Considerations

### Memory Usage

- Window duration: ~30s window ≈ 480KB (16kHz mono F32)
- Model size: ~100-500MB depending on model
- Inference queue: ~10 windows ≈ 5MB

### CPU/GPU Usage

- GPU inference: ~10-50ms per 30s window
- CPU inference: ~500-2000ms per 30s window
- Use GPU for real-time processing

### Latency

Normal mode:
- Window duration: 30s
- Overlap: 5s
- Processing time: ~10-50ms (GPU)
- Total latency: ~30-35s

Low-latency mode:
- Window duration: 10s
- Overlap: 2s
- Processing time: ~5-20ms (GPU)
- Total latency: ~10-12s

---

## Thread Safety

- **PyannotePipelineManager**: Thread-safe (uses lock)
- **InferenceWorker**: Thread-safe (queue-based)
- **SignalManager**: Thread-safe (callbacks run in caller thread)
- **WebRTCHandler**: Not thread-safe (use from single thread)

---

## Error Handling

All API methods handle errors gracefully:

- Invalid parameters return `None` or raise `ValueError`
- Missing models emit error signals
- Packet loss is detected and reported
- All errors are logged via GStreamer logging

Access logs:
```bash
GST_DEBUG=pyannote:5 gst-launch-1.0 ...
```

---

## Version Compatibility

- **GStreamer**: 1.0+
- **PyTorch**: 1.11+
- **pyannote-audio**: 3.0+
- **Python**: 3.8+

---

## License

See project LICENSE file.

---

## Support

For issues and questions:
- GitHub Issues: [project repository]
- Documentation: [docs/](.)
- Examples: [examples/](../examples/)
