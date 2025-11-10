"""GStreamer Pyannote - Real-time speaker diarization element."""

__version__ = "0.1.0"

# Lazy imports to avoid loading GStreamer at package import time
# This allows testing with mocks and running in environments without GStreamer

__all__ = ["plugin_init", "__version__"]


def plugin_init(*args, **kwargs):
    """Lazy plugin initialization."""
    from gst_pyannote.plugin import plugin_init as _plugin_init

    return _plugin_init(*args, **kwargs)
