"""
Phase 3 Tests: Pyannote Pipeline Manager

Tests for the PyannotePipelineManager class that handles:
- Loading pyannote models from Hugging Face
- Model lifecycle management
- Running diarization inference
- Thread-safe operations
"""

import pytest
import torch
from unittest.mock import MagicMock, patch, PropertyMock


@pytest.mark.unit
class TestPipelineManagerInit:
    """Test PyannotePipelineManager initialization."""

    def test_manager_can_be_created(self):
        """Test that PyannotePipelineManager can be instantiated."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        assert manager is not None

    def test_manager_starts_with_no_pipeline(self):
        """Test manager initializes without a loaded pipeline."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        assert manager.pipeline is None
        assert manager.model_name is None

    def test_manager_detects_device(self):
        """Test manager detects CUDA availability."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        assert manager.device is not None
        # Should be torch.device
        assert isinstance(manager.device, torch.device)

    def test_manager_initializes_parameters(self):
        """Test manager has default parameters."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        assert isinstance(manager.params, dict)
        assert "min_speakers" in manager.params
        assert "max_speakers" in manager.params
        assert "segmentation_step" in manager.params


@pytest.mark.unit
class TestModelLoading:
    """Test model loading functionality."""

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_load_pipeline_creates_pipeline(self, mock_pipeline_class):
        """Test that load_pipeline creates a Pipeline instance."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        # Should call from_pretrained
        mock_pipeline_class.from_pretrained.assert_called_once()
        assert manager.pipeline is not None

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_load_pipeline_sets_model_name(self, mock_pipeline_class):
        """Test that loading sets the model name."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        assert manager.model_name == "pyannote/speaker-diarization-3.1"

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_load_pipeline_moves_to_device(self, mock_pipeline_class):
        """Test that pipeline is moved to the configured device."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        # Should call .to(device)
        mock_pipeline.to.assert_called_once()

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_load_pipeline_with_auth_token(self, mock_pipeline_class):
        """Test loading with HuggingFace auth token."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline(
            "pyannote/speaker-diarization-3.1",
            use_auth_token="hf_xxxxxxxxxxxx"
        )

        # Should pass token to from_pretrained
        call_kwargs = mock_pipeline_class.from_pretrained.call_args[1]
        assert call_kwargs.get("use_auth_token") == "hf_xxxxxxxxxxxx"

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_load_pipeline_handles_errors(self, mock_pipeline_class):
        """Test that loading handles errors gracefully."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline_class.from_pretrained.side_effect = Exception("Model not found")

        manager = PyannotePipelineManager()

        with pytest.raises(Exception, match="Model not found"):
            manager.load_pipeline("invalid/model")


@pytest.mark.unit
class TestModelUnloading:
    """Test model unloading and cleanup."""

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    @patch('gst_pyannote.pipeline_manager.torch')
    def test_unload_pipeline_clears_pipeline(self, mock_torch, mock_pipeline_class):
        """Test that unload clears the pipeline reference."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        assert manager.pipeline is not None

        manager.unload_pipeline()

        assert manager.pipeline is None

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    @patch('gst_pyannote.pipeline_manager.torch')
    def test_unload_pipeline_clears_model_name(self, mock_torch, mock_pipeline_class):
        """Test that unload clears the model name."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")
        manager.unload_pipeline()

        assert manager.model_name is None

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    @patch('gst_pyannote.pipeline_manager.torch')
    def test_unload_pipeline_clears_gpu_cache(self, mock_torch, mock_pipeline_class):
        """Test that unload clears CUDA cache."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        mock_torch.cuda.empty_cache = MagicMock()

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")
        manager.unload_pipeline()

        # Should clear GPU cache
        mock_torch.cuda.empty_cache.assert_called()

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    @patch('gst_pyannote.pipeline_manager.torch')
    def test_unload_when_no_pipeline_loaded(self, mock_torch, mock_pipeline_class):
        """Test that unload is safe when no pipeline is loaded."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()

        # Should not raise
        manager.unload_pipeline()


@pytest.mark.unit
class TestParameterManagement:
    """Test parameter updates."""

    def test_update_parameters(self):
        """Test updating pipeline parameters."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        manager.update_parameters({
            "min_speakers": 2,
            "max_speakers": 10,
        })

        assert manager.params["min_speakers"] == 2
        assert manager.params["max_speakers"] == 10

    def test_update_parameters_partial(self):
        """Test partial parameter updates."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        original_step = manager.params["segmentation_step"]

        manager.update_parameters({"min_speakers": 3})

        assert manager.params["min_speakers"] == 3
        # Other params unchanged
        assert manager.params["segmentation_step"] == original_step

    def test_get_parameters(self):
        """Test getting current parameters."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        manager.update_parameters({"min_speakers": 5})

        params = manager.get_parameters()
        assert params["min_speakers"] == 5


@pytest.mark.unit
class TestAudioProcessing:
    """Test audio processing and diarization."""

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_audio_requires_loaded_pipeline(self, mock_pipeline_class):
        """Test that process_audio raises when no pipeline is loaded."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        audio = torch.randn(1, 16000)

        with pytest.raises(RuntimeError, match="No pipeline loaded"):
            manager.process_audio(audio, 16000, 0.0)

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_audio_calls_pipeline(self, mock_pipeline_class):
        """Test that process_audio calls the pipeline."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        # Mock diarization result
        mock_result = MagicMock()
        mock_result.labels.return_value = ["SPEAKER_00", "SPEAKER_01"]
        mock_result.itertracks.return_value = []
        mock_pipeline.return_value = mock_result

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        audio = torch.randn(1, 16000)
        result = manager.process_audio(audio, 16000, 0.0)

        # Pipeline should be called
        mock_pipeline.assert_called_once()

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_audio_creates_proper_input(self, mock_pipeline_class):
        """Test that audio is formatted correctly for pipeline."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        mock_result = MagicMock()
        mock_result.labels.return_value = []
        mock_result.itertracks.return_value = []
        mock_pipeline.return_value = mock_result

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        audio = torch.randn(1, 16000)
        manager.process_audio(audio, 16000, 0.0)

        # Check call args - should be dict with waveform and sample_rate
        call_args = mock_pipeline.call_args[0][0]
        assert isinstance(call_args, dict)
        assert "waveform" in call_args
        assert "sample_rate" in call_args

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_audio_passes_parameters(self, mock_pipeline_class):
        """Test that min/max speakers are passed to pipeline."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        mock_result = MagicMock()
        mock_result.labels.return_value = []
        mock_result.itertracks.return_value = []
        mock_pipeline.return_value = mock_result

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")
        manager.update_parameters({"min_speakers": 2, "max_speakers": 5})

        audio = torch.randn(1, 16000)
        manager.process_audio(audio, 16000, 0.0)

        # Check kwargs
        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs.get("min_speakers") == 2
        assert call_kwargs.get("max_speakers") == 5

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_audio_returns_formatted_results(self, mock_pipeline_class):
        """Test that results are properly formatted."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        # Mock diarization with segments
        mock_segment = MagicMock()
        mock_segment.start = 1.0
        mock_segment.end = 3.0

        mock_result = MagicMock()
        mock_result.labels.return_value = ["SPEAKER_00"]
        mock_result.itertracks.return_value = [
            (mock_segment, None, "SPEAKER_00")
        ]
        mock_pipeline.return_value = mock_result

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        audio = torch.randn(1, 16000)
        result = manager.process_audio(audio, 16000, 0.0)

        # Should return dict with events
        assert isinstance(result, dict)
        assert "events" in result
        assert "speakers" in result
        assert "SPEAKER_00" in result["speakers"]

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_audio_adjusts_timestamps(self, mock_pipeline_class):
        """Test that timestamps are adjusted by start_time."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        mock_segment = MagicMock()
        mock_segment.start = 1.0
        mock_segment.end = 3.0

        mock_result = MagicMock()
        mock_result.labels.return_value = ["SPEAKER_00"]
        mock_result.itertracks.return_value = [
            (mock_segment, None, "SPEAKER_00")
        ]
        mock_pipeline.return_value = mock_result

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        audio = torch.randn(1, 16000)
        # Pass start_time = 10.0
        result = manager.process_audio(audio, 16000, 10.0)

        # Timestamps should be offset
        event = result["events"][0]
        assert event["start"] == 11.0  # 1.0 + 10.0
        assert event["end"] == 13.0    # 3.0 + 10.0


@pytest.mark.unit
class TestThreadSafety:
    """Test thread-safe operations."""

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_has_lock(self, mock_pipeline_class):
        """Test that manager has a threading lock."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager
        import threading

        manager = PyannotePipelineManager()
        assert hasattr(manager, "lock")
        assert isinstance(manager.lock, type(threading.Lock()))

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_load_acquires_lock(self, mock_pipeline_class):
        """Test that load_pipeline uses the lock."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()

        # Mock the lock
        manager.lock = MagicMock()
        manager.lock.__enter__ = MagicMock()
        manager.lock.__exit__ = MagicMock()

        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        # Lock should be used
        manager.lock.__enter__.assert_called()

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_process_acquires_lock(self, mock_pipeline_class):
        """Test that process_audio uses the lock."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline
        mock_result = MagicMock()
        mock_result.labels.return_value = []
        mock_result.itertracks.return_value = []
        mock_pipeline.return_value = mock_result

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        # Mock the lock for process call
        manager.lock = MagicMock()
        manager.lock.__enter__ = MagicMock()
        manager.lock.__exit__ = MagicMock()

        audio = torch.randn(1, 16000)
        manager.process_audio(audio, 16000, 0.0)

        # Lock should be used
        manager.lock.__enter__.assert_called()


@pytest.mark.unit
class TestStateQueries:
    """Test state query methods."""

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_is_loaded_false_initially(self, mock_pipeline_class):
        """Test is_loaded returns False when no pipeline."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        manager = PyannotePipelineManager()
        assert manager.is_loaded() is False

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    def test_is_loaded_true_after_load(self, mock_pipeline_class):
        """Test is_loaded returns True after loading."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")

        assert manager.is_loaded() is True

    @patch('gst_pyannote.pipeline_manager.Pipeline')
    @patch('gst_pyannote.pipeline_manager.torch')
    def test_is_loaded_false_after_unload(self, mock_torch, mock_pipeline_class):
        """Test is_loaded returns False after unloading."""
        from gst_pyannote.pipeline_manager import PyannotePipelineManager

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        manager = PyannotePipelineManager()
        manager.load_pipeline("pyannote/speaker-diarization-3.1")
        manager.unload_pipeline()

        assert manager.is_loaded() is False
