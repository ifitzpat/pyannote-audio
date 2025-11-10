# GStreamer Pyannote - Implementation Summary

## Project Overview

This project implements a GStreamer element that wraps pyannote-audio for real-time speaker diarization. The element accepts audio streams and outputs JSON-formatted diarization events with speaker labels and timestamps.

## Development Approach: Test-Driven Development (TDD)

All development follows strict TDD methodology:
1. **Red**: Write tests that fail
2. **Green**: Implement minimal code to pass tests
3. **Refactor**: Improve code while keeping tests passing

## Current Status

### ✅ Phase 1: Basic Element Structure (COMPLETE)

**Tests**: 12/12 passing
**Files**:
- `gst_pyannote/element.py` - Main GstPyannote class
- `gst_pyannote/pads.py` - Pad template definitions
- `gst_pyannote/plugin.py` - Plugin registration
- `tests/test_structure.py` - Structure validation tests

**Features**:
- Element inherits from `GstBase.BaseTransform`
- Four pads: `audio_sink`, `audio_src`, `json_src`, `control_sink`
- Seven GObject properties for configuration
- Pass-through mode for audio forwarding
- Proper GStreamer metadata and registration

**Properties**:
```python
model-name: str = "pyannote/speaker-diarization-3.1"
min-speakers: int = 0  # 0 = auto
max-speakers: int = 0  # 0 = auto
window-duration: float = 30.0  # seconds
overlap-duration: float = 5.0  # seconds
inference-enabled: bool = True
device: str = "cuda"
```

---

### ✅ Phase 2: Audio Buffering & Preprocessing (COMPLETE)

**Tests**: 38/38 passing
**Files**:
- `gst_pyannote/audio_buffer.py` - AudioRingBuffer class
- `gst_pyannote/audio_preprocessor.py` - AudioPreprocessor class
- `tests/test_audio_buffer.py` - Buffer tests (17 tests)
- `tests/test_audio_preprocessor.py` - Preprocessor tests (21 tests)

#### AudioRingBuffer

Manages sliding window audio accumulation:

```python
buffer = AudioRingBuffer(
    window_duration=30.0,    # 30 second windows
    overlap_duration=5.0,     # 5 second overlap
    sample_rate=16000
)

# Push audio chunks
result = buffer.push(audio_chunk)  # torch.Tensor (1, samples)

if result:
    audio_window, start_time, end_time = result
    # Process window...
```

**Key Features**:
- Automatic window emission when ready
- Overlapping windows for smooth transitions
- Timestamp tracking across windows
- Dynamic buffer expansion
- Reset capability

**Test Coverage**:
- Initialization and configuration ✅
- Window size calculations ✅
- Audio accumulation ✅
- Window emission timing ✅
- Overlapping window behavior ✅
- Timestamp correctness ✅
- Buffer reset ✅
- State properties ✅

#### AudioPreprocessor

Handles audio format conversion and preprocessing:

```python
preprocessor = AudioPreprocessor(target_rate=16000)

# Full pipeline
tensor = preprocessor.process(
    audio_np,           # numpy array
    source_rate=48000,
    channels=2,
    format_str="F32LE",
    to_mono=True
)
# Returns: torch.Tensor (1, samples) at 16kHz

# Or from GstBuffer directly
tensor = preprocessor.from_gst_buffer(gst_buffer, caps)
```

**Key Features**:
- Format conversion (S16LE, F32LE)
- Sample rate conversion with caching
- Multi-channel to mono downmixing
- Deinterleaving
- GstBuffer extraction

**Supported Formats**:
- **S16LE**: 16-bit signed int → normalized float32 [-1, 1]
- **F32LE**: 32-bit float → passthrough

**Test Coverage**:
- NumPy to tensor conversion ✅
- Format normalization ✅
- Stereo/multi-channel downmixing ✅
- Sample rate conversion ✅
- Resampler caching ✅
- Full preprocessing pipeline ✅
- GstBuffer extraction ✅

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GstPyannote Element                     │
│                                                             │
│  Audio In (F32LE, 1-2ch, 8-48kHz)                          │
│       ↓                                                     │
│  AudioPreprocessor                                          │
│   - Format conversion (S16LE → F32LE)                       │
│   - Stereo → Mono downmix                                   │
│   - Resample → 16kHz                                        │
│       ↓                                                     │
│  AudioRingBuffer                                            │
│   - Accumulate 30s windows                                  │
│   - 5s overlap between windows                              │
│   - Emit (window, start, end)                               │
│       ↓                                                     │
│  [TODO: Pyannote Pipeline]                                  │
│   - Speaker diarization                                     │
│   - Clustering                                              │
│       ↓                                                     │
│  JSON Output                                                │
│   - Diarization events                                      │
│   - Speaker labels                                          │
│   - Timestamps                                              │
│                                                             │
│  Audio Out (pass-through)                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing Strategy

### Unit Tests
- Mock-based for GStreamer components
- No runtime GStreamer dependency for CI/CD
- Focus on logic and data transformations

### Test Files
1. `tests/test_structure.py` - Element structure validation
2. `tests/test_audio_buffer.py` - Buffer behavior
3. `tests/test_audio_preprocessor.py` - Audio processing
4. `tests/test_element_basic.py` - Full GStreamer integration (requires GStreamer)
5. `tests/test_element_mock.py` - Mocked element tests

### Running Tests

```bash
# All tests
pytest

# Unit tests only (no GStreamer required)
pytest -m unit

# Integration tests (requires GStreamer)
pytest -m integration

# Specific phase
pytest tests/test_audio_buffer.py -v
```

---

## Code Statistics

| Component | Files | Lines | Tests |
|-----------|-------|-------|-------|
| Element Core | 3 | ~350 | 12 |
| Audio Processing | 2 | ~450 | 38 |
| **Total** | **5** | **~800** | **50** |

**Test Pass Rate**: 100% (50/50)

---

## Next Steps (Phase 3)

### Pyannote Integration

**Goals**:
1. Implement `PyannotePipelineManager`
2. Model loading/unloading
3. Inference worker thread
4. Error handling
5. Integrate with AudioRingBuffer

**Components to Build**:
- `gst_pyannote/pipeline_manager.py` - Pyannote pipeline wrapper
- `gst_pyannote/inference_worker.py` - Background inference thread
- Tests for pipeline management
- Tests for thread safety
- Tests for model lifecycle

**Expected Test Count**: ~25 new tests

---

## Dependencies

### Required
- Python >= 3.10
- PyTorch >= 2.0
- torchaudio >= 2.0
- PyGObject >= 3.42 (for GStreamer bindings)
- pyannote-audio >= 3.0

### Development
- pytest >= 7.0
- pytest-cov >= 4.0
- pytest-mock >= 3.10
- black (code formatting)
- flake8 (linting)

---

## Usage Example (When Complete)

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

# Create pipeline
pipeline = Gst.parse_launch("""
    pipewiresrc !
    audioconvert !
    audio/x-raw,format=F32LE,rate=16000,channels=1 !
    pyannote
        model-name=pyannote/speaker-diarization-3.1
        min-speakers=2
        max-speakers=10
        window-duration=30 !
    filesink location=diarization.json
""")

# Connect to signals
pyannote = pipeline.get_by_name("pyannote")
pyannote.connect("speaker-joined", on_speaker_joined)
pyannote.connect("speaker-speaking", on_speaker_speaking)

# Run
pipeline.set_state(Gst.State.PLAYING)
```

---

## Project Structure

```
gst-pyannote/
├── gst_pyannote/
│   ├── __init__.py              # Package init (lazy imports)
│   ├── element.py               # Main GstPyannote element ✅
│   ├── pads.py                  # Pad templates ✅
│   ├── plugin.py                # Plugin registration ✅
│   ├── audio_buffer.py          # AudioRingBuffer ✅
│   ├── audio_preprocessor.py   # AudioPreprocessor ✅
│   ├── pipeline_manager.py      # TODO: Phase 3
│   └── inference_worker.py      # TODO: Phase 3
├── tests/
│   ├── conftest.py              # Pytest configuration
│   ├── test_structure.py        # Element structure tests ✅
│   ├── test_audio_buffer.py     # Buffer tests ✅
│   ├── test_audio_preprocessor.py  # Preprocessor tests ✅
│   ├── test_element_basic.py    # Integration tests
│   └── test_element_mock.py     # Mocked element tests
├── examples/                    # TODO: Usage examples
├── docs/                        # TODO: Documentation
├── pyproject.toml              # Project configuration
├── setup.py                    # Setup script
├── README.md                   # Project README
└── PROGRESS.md                 # Implementation progress

```

---

## Key Design Decisions

### 1. Test-Driven Development
- All code written after tests
- Ensures correctness from the start
- Comprehensive test coverage

### 2. Lazy Imports
- GStreamer modules imported only when needed
- Allows testing without full GStreamer stack
- Better for CI/CD environments

### 3. Mock-Based Testing
- Unit tests use mocks for GStreamer components
- Integration tests marked separately
- Fast test execution

### 4. Modular Architecture
- Separate concerns (buffering, preprocessing, inference)
- Each component independently testable
- Easy to extend or replace components

### 5. PyTorch Native
- All audio processing in PyTorch tensors
- Seamless integration with pyannote-audio
- GPU acceleration ready

---

## Performance Considerations

### Memory
- Ring buffer pre-allocates 2x window size
- Dynamic expansion as needed
- Resampler caching to avoid recreation

### CPU/GPU
- Preprocessing happens on CPU
- Inference will use GPU (Phase 3)
- Worker thread decouples streaming from processing

### Latency
- 30s windows with 5s overlap = 25s step
- ~2-5s inference time (GPU)
- Total latency: ~27-30s from audio to results

---

## License

MIT License - See LICENSE file for details
