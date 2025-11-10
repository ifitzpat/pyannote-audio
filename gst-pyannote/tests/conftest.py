"""Pytest configuration and fixtures for gst-pyannote tests."""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def gst_init():
    """Initialize GStreamer for tests."""
    try:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        return Gst
    except (ImportError, ValueError) as e:
        pytest.skip(f"GStreamer not available: {e}")


@pytest.fixture
def gst_element_factory(gst_init):
    """Factory fixture for creating GStreamer elements."""

    def _create_element(factory_name, name=None):
        element = gst_init.ElementFactory.make(factory_name, name)
        if element is None:
            pytest.skip(f"GStreamer element '{factory_name}' not available")
        return element

    return _create_element


@pytest.fixture
def sample_audio_caps(gst_init):
    """Fixture providing common audio caps for testing."""
    return {
        "f32le_mono_16k": gst_init.Caps.from_string(
            "audio/x-raw,format=F32LE,rate=16000,channels=1,layout=interleaved"
        ),
        "f32le_stereo_16k": gst_init.Caps.from_string(
            "audio/x-raw,format=F32LE,rate=16000,channels=2,layout=interleaved"
        ),
        "s16le_mono_16k": gst_init.Caps.from_string(
            "audio/x-raw,format=S16LE,rate=16000,channels=1,layout=interleaved"
        ),
        "f32le_mono_48k": gst_init.Caps.from_string(
            "audio/x-raw,format=F32LE,rate=48000,channels=1,layout=interleaved"
        ),
    }


@pytest.fixture
def mock_pipeline_manager(mocker):
    """Mock PyannotePipelineManager for testing without actual models."""
    mock = mocker.MagicMock()
    mock.pipeline = None
    mock.model_name = None
    mock.params = {
        "min_speakers": None,
        "max_speakers": None,
        "segmentation_step": 0.1,
        "embedding_batch_size": 32,
        "clustering": "AgglomerativeClustering",
    }
    return mock
