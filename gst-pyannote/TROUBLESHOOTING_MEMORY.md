# Troubleshooting std::bad_alloc on Import

This guide addresses `std::bad_alloc` (C++ memory allocation failure) occurring during `import` of gst-pyannote, particularly in GNU Guix environments.

> **UPDATE:** The root cause has been identified as **torchcodec initialization**, not CUDA. See [TORCHCODEC_ANALYSIS.md](TORCHCODEC_ANALYSIS.md) for complete details.
>
> **Quick fix:** `pip uninstall torchcodec -y`

## Identified Potential Causes

### 0. **torchcodec Initialization (CONFIRMED ROOT CAUSE)**

**See:** [TORCHCODEC_ANALYSIS.md](TORCHCODEC_ANALYSIS.md) for complete analysis.

**Summary:** torchcodec is a PyTorch library that wraps FFmpeg for audio/video decoding. When imported, it:
- Initializes FFmpeg codec contexts
- Probes hardware decoders (VAAPI, VDPAU, CUDA)
- Has known compatibility issues with PyTorch 2.9.0+cpu

**Location:** Triggered by `import pyannote.audio` → `pyannote.audio.core.io` → `import torchcodec`

**Quick Solution:**
```bash
pip uninstall torchcodec -y
```

**Why it works:** gst-pyannote doesn't need file I/O (uses GStreamer buffers), so torchcodec is unnecessary for your use case.

**Alternative solutions:** See TORCHCODEC_ANALYSIS.md for building from source or downgrading PyTorch.

### 1. **CUDA Context Initialization (Most Likely)**

**Location:** `gst_pyannote/pipeline_manager.py:39`

```python
self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

**Problem:** When `PyannotePipelineManager` is created with `device=None`, it calls `torch.cuda.is_available()` which:
- Initializes CUDA runtime
- Allocates CUDA context (~500MB+)
- May fail with `std::bad_alloc` if:
  - CUDA driver version mismatch
  - Insufficient VRAM (though you said you have plenty)
  - CUDA library compatibility issues in GNU Guix
  - PTX/JIT compilation issues

**Solution:**
```python
# Modify pipeline_manager.py line 37-41 to delay CUDA check:
if device is None:
    # Don't check CUDA availability during init
    self.device = torch.device("cpu")  # Default to CPU
else:
    self.device = torch.device(device)
```

Or set device explicitly:
```python
manager = PyannotePipelineManager(device="cpu")  # Avoid CUDA check
```

### 2. **AudioRingBuffer Tensor Allocation**

**Location:** `gst_pyannote/audio_buffer.py:46`

```python
self.buffer = torch.zeros(1, self.window_samples * 2, dtype=torch.float32)
```

**Memory usage with defaults:**
- `window_duration = 30.0` seconds
- `sample_rate = 16000` Hz
- Buffer size = 2 × 30 × 16000 = 960,000 floats
- Memory = 960,000 × 4 bytes = **3.84 MB**

**Problem:** If PyTorch allocator is corrupted or CUDA is trying to allocate this on GPU, it could fail.

**Solution:**
```python
# Ensure CPU allocation
self.buffer = torch.zeros(
    1, self.window_samples * 2,
    dtype=torch.float32,
    device='cpu'  # Explicit CPU allocation
)
```

### 3. **pyannote.audio Import**

The `pyannote.audio` library itself may be causing the issue during import.

**Test:**
```python
import sys
import traceback

try:
    print("Importing torch...")
    import torch
    print(f"✅ torch {torch.__version__}")

    print("Importing torchaudio...")
    import torchaudio
    print(f"✅ torchaudio {torchaudio.__version__}")

    print("Importing pyannote.audio...")
    from pyannote.audio import Pipeline
    print("✅ pyannote.audio")

except Exception as e:
    print(f"❌ Failed at: {e}")
    traceback.print_exc()
```

**Possible causes:**
- pyannote.audio loads models during import (shouldn't, but check)
- Large pre-trained weights being downloaded
- ONNX runtime initialization
- Hugging Face hub issues

### 4. **Torchaudio Resampler**

**Location:** `gst_pyannote/audio_preprocessor.py:118-123`

```python
if source_rate not in self.resamplers:
    self.resamplers[source_rate] = torchaudio.transforms.Resample(
        orig_freq=source_rate,
        new_freq=self.target_rate,
    )
```

**Problem:** `Resample` compiles resampling kernels which:
- Allocates kernel weights
- May JIT-compile CUDA kernels
- Can fail in constrained environments

**Solution:**
```python
# Ensure CPU resampler
self.resamplers[source_rate] = torchaudio.transforms.Resample(
    orig_freq=source_rate,
    new_freq=self.target_rate,
).cpu()  # Force CPU
```

### 5. **GNU Guix Library Compatibility**

GNU Guix packages libraries differently than typical Linux distributions.

**Potential issues:**
- CUDA library paths not found
- cuDNN version mismatch
- libcudart incompatibility
- Conda/system library conflicts

**Check:**
```bash
# Check CUDA libraries
ldd $(python3 -c "import torch; print(torch.__file__)") | grep cuda

# Check for multiple CUDA installations
find /gnu/store -name "libcudart*" 2>/dev/null
```

## Diagnostic Steps

### Step 1: Isolate the Import

Create `test_import.py`:

```python
#!/usr/bin/env python3
import sys
import os

# Disable CUDA completely
os.environ['CUDA_VISIBLE_DEVICES'] = ''

print("=== Import Test ===")

modules = [
    ("PyTorch", "torch"),
    ("TorchAudio", "torchaudio"),
    ("NumPy", "numpy"),
    ("PyAnnote Audio Pipeline", "pyannote.audio"),
    ("PyAnnote Audio Pipeline.Pipeline", "pyannote.audio.Pipeline"),
]

for name, module_path in modules:
    try:
        print(f"\nImporting {name}...", end=" ")
        parts = module_path.split('.')

        if len(parts) == 1:
            __import__(module_path)
        else:
            module = __import__(parts[0])
            for part in parts[1:]:
                module = getattr(module, part)

        print("✅ Success")

    except Exception as e:
        print(f"❌ FAILED")
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\n⚠️  Failure occurred here!")
        sys.exit(1)

print("\n✅ All imports successful")

# Now test gst_pyannote
print("\nImporting gst_pyannote...")
try:
    import gst_pyannote
    print(f"✅ gst_pyannote {gst_pyannote.__version__}")
except Exception as e:
    print(f"❌ gst_pyannote failed: {e}")
    import traceback
    traceback.print_exc()
```

Run with:
```bash
python3 test_import.py
```

### Step 2: Check Memory Limits

```bash
# Check available memory
free -h

# Check ulimits
ulimit -a

# Check cgroups (if in container)
cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null
```

### Step 3: Trace Memory Allocation

```bash
# Run with memory tracing
python3 -X tracemalloc test_import.py

# Or use ltrace to see allocation calls
ltrace -e malloc,calloc,realloc python3 test_import.py 2>&1 | grep -i bad

# Or use strace
strace -e brk,mmap python3 test_import.py 2>&1 | tail -100
```

### Step 4: Test with Minimal PyTorch

```python
import torch
import sys

print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CPU threads: {torch.get_num_threads()}")

# Try allocation
try:
    print("\nAllocating small CPU tensor...")
    x = torch.zeros(100)
    print("✅ CPU allocation OK")

    print("\nAllocating medium CPU tensor (4MB)...")
    y = torch.zeros(1000000)
    print("✅ Medium CPU allocation OK")

    print("\nAllocating large CPU tensor (40MB)...")
    z = torch.zeros(10000000)
    print("✅ Large CPU allocation OK")

except Exception as e:
    print(f"❌ Allocation failed: {e}")
    sys.exit(1)
```

## Solutions

### Solution 1: Force CPU-Only Mode

Create a wrapper script `run_gst_pyannote.sh`:

```bash
#!/bin/bash

# Disable CUDA completely
export CUDA_VISIBLE_DEVICES=""
export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:32"

# Use CPU-only PyTorch
export TORCH_USE_CUDA_DSA=0

# Run your application
python3 your_application.py "$@"
```

### Solution 2: Modify PyannotePipelineManager

**File:** `gst_pyannote/pipeline_manager.py`

```python
def __init__(self, device: Optional[str] = None):
    """
    Initialize pipeline manager.

    Parameters
    ----------
    device : str, optional
        PyTorch device to use ("cuda", "cpu", etc.)
        Default: "cpu" (changed from auto-detect)
    """
    # Determine device - default to CPU to avoid CUDA initialization
    if device is None:
        self.device = torch.device("cpu")  # Changed from auto-detect
        # Only check CUDA if explicitly needed later
    else:
        self.device = torch.device(device)

    self.pipeline = None
    self.model_name = None
    self.lock = threading.Lock()
    self.parameters = {}
```

### Solution 3: Lazy CUDA Detection

```python
def __init__(self, device: Optional[str] = None):
    # Don't initialize device yet
    self._device_str = device
    self._device = None
    self.pipeline = None
    self.model_name = None
    self.lock = threading.Lock()
    self.parameters = {}

@property
def device(self):
    """Lazy device initialization."""
    if self._device is None:
        if self._device_str is None:
            # Only check CUDA when actually needed
            try:
                if torch.cuda.is_available():
                    self._device = torch.device("cuda")
                else:
                    self._device = torch.device("cpu")
            except Exception:
                # If CUDA check fails, fall back to CPU
                self._device = torch.device("cpu")
        else:
            self._device = torch.device(self._device_str)
    return self._device
```

### Solution 4: Fix GNU Guix Library Paths

If using GNU Guix:

```bash
# Add to your Guix profile or shell.scm
export LD_LIBRARY_PATH="/gnu/store/...-cuda-toolkit/lib:$LD_LIBRARY_PATH"
export CUDA_HOME="/gnu/store/...-cuda-toolkit"

# Or create a Guix manifest.scm with proper CUDA packages
```

### Solution 5: Use CPU-Only PyTorch

Reinstall PyTorch CPU-only version:

```bash
# Uninstall current PyTorch
pip uninstall torch torchaudio

# Install CPU-only version
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Quick Fix (Immediate Relief)

Add this to the **very beginning** of your Python script **before any imports**:

```python
#!/usr/bin/env python3
import os
import sys

# CRITICAL: Set BEFORE importing torch/pyannote
os.environ['CUDA_VISIBLE_DEVICES'] = ''  # Disable CUDA
os.environ['OMP_NUM_THREADS'] = '4'       # Limit CPU threads
os.environ['MKL_NUM_THREADS'] = '4'       # Limit MKL threads

# Reduce PyTorch memory allocation
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'

# Now safe to import
import torch
torch.set_num_threads(4)  # Limit threads

# Continue with your imports
import gst_pyannote
# ...
```

## Verification

After applying fixes, verify:

```bash
# Test import
python3 -c "import gst_pyannote; print('✅ Import successful')"

# Test basic functionality
python3 -c "
from gst_pyannote.audio_buffer import AudioRingBuffer
buf = AudioRingBuffer()
print(f'✅ AudioRingBuffer created: {buf.buffer.shape}')
"

# Test pipeline manager
python3 -c "
from gst_pyannote.pipeline_manager import PyannotePipelineManager
mgr = PyannotePipelineManager(device='cpu')
print(f'✅ PipelineManager created: device={mgr.device}')
"
```

## GNU Guix Specific

If you're in a Guix environment, create `guix-fix.scm`:

```scheme
(use-modules (gnu packages))

(specifications->manifest
  '("python"
    "python-pytorch"  ; CPU-only version
    "python-numpy"
    "python-scipy"
    "python-pyaudio"
    "gstreamer"
    "gst-plugins-base"
    "gst-plugins-good"))
```

Then:
```bash
guix shell -m guix-fix.scm
```

## Summary

Most likely cause: **CUDA initialization in `PyannotePipelineManager.__init__`**

Most effective fix: **Set `CUDA_VISIBLE_DEVICES=''` before import**

Permanent solution: **Modify `pipeline_manager.py` to default to CPU instead of auto-detecting CUDA**

---

If you continue experiencing issues after trying these solutions, please provide:
1. Output of `test_import.py`
2. Your GNU Guix package versions
3. PyTorch installation method
4. Full error traceback with `strace` or `ltrace`
