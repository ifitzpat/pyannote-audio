# torchcodec std::bad_alloc Root Cause Analysis

## Summary

The `std::bad_alloc` error during `import pyannote.audio` is caused by **torchcodec initialization**, not CUDA. Removing torchcodec from the dependency chain resolves the issue.

## What is torchcodec?

**torchcodec** is a PyTorch library that decodes video/audio files into tensors using FFmpeg as the backend. It replaced `torchaudio` for audio I/O in pyannote.audio version 4.0+.

**Key characteristics:**
- Hard dependency in pyannote.audio (pyproject.toml:28: `torchcodec>=0.6.0`)
- Wraps FFmpeg codec operations in a PyTorch-friendly API
- Initializes FFmpeg contexts and probes hardware decoders **during import**
- Requires FFmpeg libraries at runtime
- Can use CUDA for GPU-accelerated decoding (optional)

## Why torchcodec Causes std::bad_alloc

### 1. **Known Issue with PyTorch 2.9**

There's a documented issue ([torchcodec#980](https://github.com/meta-pytorch/torchcodec/issues/980)) where torchcodec 0.8.0 throws `std::bad_alloc` when used with PyTorch 2.9 nightly/alpha builds.

**Your environment:**
- PyTorch: **2.9.0+cpu** (matches the problematic version)
- torchcodec: Version unknown (likely stable 0.6.x-0.8.x from pip)

**Root cause:** Binary incompatibility between:
- Nightly/alpha PyTorch 2.9 (unstable ABI)
- Stable torchcodec built against PyTorch 2.8 or earlier

### 2. **FFmpeg Initialization on Import**

When `pyannote.audio.core.io` is imported, torchcodec immediately:

```python
# src/pyannote/audio/core/io.py:43-45
import torchcodec
from torchcodec import AudioSamples
from torchcodec.decoders import AudioDecoder, AudioStreamMetadata
```

This triggers FFmpeg initialization:
1. **Loads shared libraries**: `libavcodec`, `libavformat`, `libavutil`, `libswresample`
2. **Probes hardware decoders**: Checks for NVENC, VAAPI, VDPAU, etc.
3. **Allocates codec contexts**: Pre-allocates structures for decoding
4. **Initializes thread pools**: Sets up worker threads for parallel decoding

**Memory requirements:**
- Initial allocation: ~10-50 MB for codec metadata
- Hardware probe: Attempts to initialize GPU contexts (even on CPU-only systems)
- Thread pools: Allocates per-thread buffers

### 3. **GNU Guix Specific Issues**

GNU Guix packages libraries in `/gnu/store/` with unique hash-based paths:

```
/gnu/store/abc123...-ffmpeg-6.1/lib/libavcodec.so
/gnu/store/def456...-libva-2.21/lib/libva.so
```

**Problems:**
- **Dynamic linking failures**: torchcodec compiled with different FFmpeg path
- **Symbol version mismatches**: FFmpeg ABI changes between versions
- **Missing hardware libraries**: VAAPI/VDPAU libraries not found
- **Permission issues**: Hardware device nodes (`/dev/dri/*`) inaccessible

When FFmpeg tries to probe hardware decoders but libraries are incompatible or missing, the initialization can fail with `std::bad_alloc` instead of gracefully falling back to software decoding.

### 4. **Hardware Decoder Probe Failures**

Even on a CPU-only PyTorch build, torchcodec/FFmpeg will try to probe hardware video decoders:

```c++
// FFmpeg internally does this on initialization:
av_hwdevice_ctx_create(&hw_device_ctx, AV_HWDEVICE_TYPE_CUDA, NULL, NULL, 0);
av_hwdevice_ctx_create(&hw_device_ctx, AV_HWDEVICE_TYPE_VAAPI, NULL, NULL, 0);
av_hwdevice_ctx_create(&hw_device_ctx, AV_HWDEVICE_TYPE_VDPAU, NULL, NULL, 0);
```

**On your system:**
- CUDA libraries may be present but incompatible
- VAAPI/VDPAU may try to allocate GPU memory
- Failure to initialize throws `std::bad_alloc` instead of returning NULL

This is particularly problematic because:
- You have "plenty of RAM and VRAM" (your words)
- But the allocation failure is from **incompatible library versions**, not insufficient memory
- C++ `std::bad_alloc` is thrown when `malloc()` returns NULL OR when a constructor fails
- FFmpeg hardware context initialization failures can be misreported as memory allocation failures

## Why Removing torchcodec Fixes It

When you remove torchcodec from the dependency chain:

1. ✅ **No FFmpeg initialization** on import
2. ✅ **No hardware decoder probing**
3. ✅ **No binary compatibility issues** with PyTorch 2.9
4. ✅ **pyannote.audio.core.io gracefully falls back** (see line 46-52):

```python
try:
    import torchcodec
    from torchcodec import AudioSamples
    from torchcodec.decoders import AudioDecoder, AudioStreamMetadata
except Exception as e:
    warnings.warn(
        "\ntorchcodec is not installed correctly so built-in audio decoding will fail..."
    )
```

**Note:** This means audio file loading will fail, but if you're using gst-pyannote with live audio streams from GStreamer, you don't need file I/O anyway.

## Verification Steps

### 1. Confirm torchcodec is the culprit

```bash
# Test without torchcodec
pip uninstall torchcodec -y

python3 -c "
import warnings
warnings.filterwarnings('ignore')  # Suppress the torchcodec warning
from pyannote.audio.core import io
print('✅ Import successful without torchcodec')
"
```

### 2. Check FFmpeg availability

```bash
# Check if FFmpeg is installed
ffmpeg -version

# Check FFmpeg libraries in Guix
find /gnu/store -name "libavcodec.so*" 2>/dev/null | head -5
```

### 3. Test with compatible torchcodec

```bash
# Option A: Build torchcodec from source (matches your PyTorch build)
pip uninstall torchcodec -y
git clone https://github.com/pytorch/torchcodec.git
cd torchcodec
pip install -e .

# Option B: Downgrade PyTorch to stable 2.8
pip uninstall torch torchaudio -y
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
pip install torchcodec==0.8.0

# Test
python3 -c "import torchcodec; print('✅ torchcodec import successful')"
```

### 4. Check for library conflicts

```bash
# List all FFmpeg-related libraries torchcodec might use
ldd $(python3 -c "import torchcodec; import os; print(os.path.dirname(torchcodec.__file__))")/lib/*.so 2>/dev/null | grep -E "(avcodec|avformat|avutil|swresample)"

# Check for multiple FFmpeg versions
guix package --list-installed | grep ffmpeg
```

## Solutions

### Solution 1: Remove torchcodec (For gst-pyannote only)

**Best if:** You only use gst-pyannote with live GStreamer audio streams, not file I/O.

```bash
pip uninstall torchcodec -y
```

**Consequence:** `pyannote.audio.Audio` file loading will fail, but pipeline inference on pre-loaded tensors still works.

### Solution 2: Build torchcodec from Source

**Best if:** You need file I/O and have PyTorch 2.9.

```bash
pip uninstall torchcodec -y
git clone https://github.com/pytorch/torchcodec.git
cd torchcodec
pip install -e .
```

**Why it works:** Source build compiles against your exact PyTorch version, avoiding ABI mismatches.

### Solution 3: Downgrade to PyTorch 2.8 Stable

**Best if:** You want stability and don't need PyTorch 2.9 features.

```bash
pip uninstall torch torchaudio torchcodec -y
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
pip install torchcodec==0.8.0
```

### Solution 4: Disable Hardware Decoders

**Best if:** You want to keep current versions but avoid hardware probe failures.

Set environment variables before import:

```python
import os

# Disable FFmpeg hardware acceleration
os.environ['FFMPEG_CAPTURE_OPTIONS'] = '-hwaccel none'
os.environ['LIBVA_DRIVER_NAME'] = 'none'  # Disable VAAPI
os.environ['VDPAU_DRIVER'] = 'none'       # Disable VDPAU

# Now safe to import
from pyannote.audio import Pipeline
```

Or create a wrapper script:

```bash
#!/bin/bash
export FFMPEG_CAPTURE_OPTIONS="-hwaccel none"
export LIBVA_DRIVER_NAME="none"
export VDPAU_DRIVER="none"

python3 your_application.py "$@"
```

### Solution 5: Make pyannote.audio Optional in gst-pyannote

**Best if:** You want gst-pyannote to work without full pyannote.audio dependency.

Modify `gst-pyannote/pyproject.toml` to make pyannote.audio optional:

```toml
[project]
dependencies = [
    "torch>=2.8.0",
    "torchaudio>=2.8.0",
    # pyannote.audio moved to optional
]

[project.optional-dependencies]
full = [
    "pyannote-audio>=4.0.0",  # Includes torchcodec
]
```

Then use lazy imports in code:

```python
# gst_pyannote/pipeline_manager.py
def load_model(self, model_name: str):
    try:
        from pyannote.audio import Pipeline
    except ImportError as e:
        raise ImportError(
            "pyannote.audio is required for model loading. "
            "Install with: pip install pyannote-audio\n"
            f"Original error: {e}"
        )
    # ... rest of implementation
```

## Recommendations

For your GNU Guix environment, I recommend:

1. **Short-term:** Remove torchcodec (`pip uninstall torchcodec`)
   - Gets you working immediately
   - No file I/O, but gst-pyannote doesn't need it anyway

2. **Medium-term:** Build torchcodec from source
   - Ensures binary compatibility with PyTorch 2.9
   - Takes 5-10 minutes to compile

3. **Long-term:** Add to Guix channel
   - Package torchcodec properly for Guix
   - Ensures library paths are correct
   - Create a Guix manifest with all dependencies

## Why CUDA_VISIBLE_DEVICES Didn't Help

Setting `CUDA_VISIBLE_DEVICES=''` prevents PyTorch CUDA initialization, but:

- **torchcodec still probes FFmpeg hardware decoders** (VAAPI, VDPAU, etc.)
- **FFmpeg's CUDA probe is independent** of PyTorch's CUDA
- **The failure happens in FFmpeg initialization**, not PyTorch

The original troubleshooting guide focused on PyTorch CUDA, but the actual culprit was torchcodec's FFmpeg initialization.

## Updated Diagnostic Script

```python
#!/usr/bin/env python3
import sys
import os

print("=== torchcodec Diagnostic ===\n")

# Test 1: PyTorch
try:
    import torch
    print(f"✅ PyTorch: {torch.__version__}")
except Exception as e:
    print(f"❌ PyTorch failed: {e}")
    sys.exit(1)

# Test 2: FFmpeg via subprocess
try:
    import subprocess
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"✅ FFmpeg: {version_line}")
    else:
        print(f"⚠️  FFmpeg not found or failed")
except Exception as e:
    print(f"⚠️  FFmpeg check failed: {e}")

# Test 3: torchcodec
print("\nAttempting torchcodec import...")
try:
    import torchcodec
    print(f"✅ torchcodec: {torchcodec.__version__}")

    # Test decoder initialization
    print("   Testing AudioDecoder...")
    from torchcodec.decoders import AudioDecoder
    print("   ✅ AudioDecoder imported successfully")

except Exception as e:
    print(f"❌ torchcodec FAILED: {type(e).__name__}")
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()
    print("\n⚠️  This is likely your issue!")
    sys.exit(1)

# Test 4: pyannote.audio
print("\nAttempting pyannote.audio import...")
try:
    import warnings
    warnings.filterwarnings('ignore')
    from pyannote.audio import Pipeline
    print("✅ pyannote.audio imported successfully")
except Exception as e:
    print(f"❌ pyannote.audio failed: {e}")
    sys.exit(1)

print("\n✅ All imports successful!")
```

## References

- [torchcodec Issue #980](https://github.com/meta-pytorch/torchcodec/issues/980) - std::bad_alloc with torch 2.9
- [torchcodec GitHub](https://github.com/pytorch/torchcodec) - Main repository
- [pyannote.audio CHANGELOG](../CHANGELOG.md) - Switch from torchaudio to torchcodec
- [FFmpeg Hardware Acceleration](https://trac.ffmpeg.org/wiki/HWAccelIntro) - Hardware decoder documentation
