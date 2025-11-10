"""
Phase 2 Tests: Audio Preprocessing

Tests for the AudioPreprocessor class that handles:
- GstBuffer to PyTorch tensor conversion
- Sample rate conversion
- Stereo to mono downmixing
- Format conversion
"""

import pytest
import torch
import numpy as np
from unittest.mock import MagicMock, patch


@pytest.mark.unit
class TestAudioPreprocessorInit:
    """Test AudioPreprocessor initialization."""

    def test_preprocessor_can_be_created(self):
        """Test that AudioPreprocessor can be instantiated."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)
        assert preprocessor is not None
        assert preprocessor.target_rate == 16000

    def test_preprocessor_default_target_rate(self):
        """Test default target sample rate is 16kHz."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()
        assert preprocessor.target_rate == 16000


@pytest.mark.unit
class TestNumpyToTensor:
    """Test conversion from NumPy to PyTorch tensor."""

    def test_convert_mono_float32_to_tensor(self):
        """Test converting mono F32LE to tensor."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Create mono audio (1600 samples)
        audio_np = np.random.randn(1600).astype(np.float32)

        tensor = preprocessor.numpy_to_tensor(audio_np, channels=1)

        assert isinstance(tensor, torch.Tensor)
        assert tensor.shape == (1, 1600)  # (channels, samples)
        assert tensor.dtype == torch.float32

    def test_convert_stereo_to_tensor(self):
        """Test converting stereo audio to tensor."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Create stereo audio (1600 samples * 2 channels = 3200 values)
        # Interleaved: L R L R L R ...
        audio_np = np.random.randn(3200).astype(np.float32)

        tensor = preprocessor.numpy_to_tensor(audio_np, channels=2)

        assert tensor.shape == (2, 1600)  # (channels, samples)

    def test_convert_int16_to_float32(self):
        """Test converting S16LE to float32."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Create int16 audio
        audio_np = np.random.randint(-32768, 32767, size=1600, dtype=np.int16)

        tensor = preprocessor.numpy_to_tensor(audio_np, channels=1, format_str="S16LE")

        assert tensor.dtype == torch.float32
        # Values should be normalized to roughly [-1, 1]
        assert tensor.abs().max() <= 1.0

    def test_deinterleave_stereo(self):
        """Test deinterleaving stereo audio."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Create known pattern: L=1.0, R=2.0, alternating
        left = np.ones(800, dtype=np.float32)
        right = np.ones(800, dtype=np.float32) * 2.0
        interleaved = np.empty(1600, dtype=np.float32)
        interleaved[0::2] = left
        interleaved[1::2] = right

        tensor = preprocessor.numpy_to_tensor(interleaved, channels=2)

        # Check deinterleaving
        assert torch.allclose(tensor[0], torch.ones(800))
        assert torch.allclose(tensor[1], torch.ones(800) * 2.0)


@pytest.mark.unit
class TestStereoToMono:
    """Test stereo to mono downmixing."""

    def test_downmix_stereo_to_mono(self):
        """Test converting stereo to mono by averaging."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Create stereo tensor
        left = torch.ones(1, 1000) * 1.0
        right = torch.ones(1, 1000) * 3.0
        stereo = torch.cat([left, right], dim=0)  # (2, 1000)

        mono = preprocessor.stereo_to_mono(stereo)

        assert mono.shape == (1, 1000)
        # Average of 1.0 and 3.0 is 2.0
        assert torch.allclose(mono, torch.ones(1, 1000) * 2.0)

    def test_mono_passthrough(self):
        """Test that mono audio passes through unchanged."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        mono = torch.randn(1, 1000)
        result = preprocessor.stereo_to_mono(mono)

        assert torch.allclose(result, mono)

    def test_multi_channel_downmix(self):
        """Test downmixing more than 2 channels."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # 4 channels with different values
        multi = torch.tensor([
            [1.0] * 100,
            [2.0] * 100,
            [3.0] * 100,
            [4.0] * 100,
        ])

        mono = preprocessor.stereo_to_mono(multi)

        # Average of 1, 2, 3, 4 is 2.5
        assert mono.shape == (1, 100)
        assert torch.allclose(mono, torch.ones(1, 100) * 2.5)


@pytest.mark.unit
class TestSampleRateConversion:
    """Test sample rate conversion."""

    def test_resample_creates_resampler_on_demand(self):
        """Test that resampler is created when sample rates differ."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        audio = torch.randn(1, 48000)  # 1 second at 48kHz

        result = preprocessor.resample(audio, source_rate=48000)

        # Should be downsampled to 16kHz
        assert result.shape[1] == 16000

    def test_resample_passthrough_when_rates_match(self):
        """Test no resampling when rates match."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        audio = torch.randn(1, 16000)
        result = preprocessor.resample(audio, source_rate=16000)

        # Should be unchanged
        assert torch.allclose(result, audio)

    def test_resample_preserves_duration(self):
        """Test that resampling preserves duration."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        # 2 seconds at 8kHz = 16000 samples
        audio = torch.randn(1, 16000)

        result = preprocessor.resample(audio, source_rate=8000)

        # 2 seconds at 16kHz = 32000 samples
        assert result.shape[1] == 32000

    def test_resample_caches_resampler(self):
        """Test that resampler is cached for efficiency."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        audio1 = torch.randn(1, 48000)
        result1 = preprocessor.resample(audio1, source_rate=48000)

        # Should have cached a 48000->16000 resampler
        assert 48000 in preprocessor._resamplers

        # Resampling again should use cached resampler
        audio2 = torch.randn(1, 48000)
        result2 = preprocessor.resample(audio2, source_rate=48000)

        assert result2.shape[1] == 16000


@pytest.mark.unit
class TestFullPreprocessing:
    """Test complete preprocessing pipeline."""

    def test_process_mono_no_resampling(self):
        """Test processing mono audio with matching sample rate."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        # Create F32LE mono audio
        audio_np = np.random.randn(16000).astype(np.float32)

        result = preprocessor.process(
            audio_np,
            source_rate=16000,
            channels=1,
            format_str="F32LE"
        )

        assert isinstance(result, torch.Tensor)
        assert result.shape == (1, 16000)
        assert result.dtype == torch.float32

    def test_process_stereo_with_downmix(self):
        """Test processing stereo audio with downmix to mono."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        # Create stereo audio (interleaved)
        stereo_np = np.random.randn(32000).astype(np.float32)  # 16000 samples * 2 channels

        result = preprocessor.process(
            stereo_np,
            source_rate=16000,
            channels=2,
            format_str="F32LE",
            to_mono=True
        )

        # Should be downmixed to mono
        assert result.shape == (1, 16000)

    def test_process_with_resampling(self):
        """Test processing with sample rate conversion."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        # 1 second at 48kHz
        audio_np = np.random.randn(48000).astype(np.float32)

        result = preprocessor.process(
            audio_np,
            source_rate=48000,
            channels=1,
            format_str="F32LE"
        )

        # Should be resampled to 16kHz
        assert result.shape == (1, 16000)

    def test_process_stereo_48k_to_mono_16k(self):
        """Test full pipeline: stereo 48kHz → mono 16kHz."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor(target_rate=16000)

        # 1 second stereo at 48kHz = 96000 values (interleaved)
        audio_np = np.random.randn(96000).astype(np.float32)

        result = preprocessor.process(
            audio_np,
            source_rate=48000,
            channels=2,
            format_str="F32LE",
            to_mono=True
        )

        # Final: mono 16kHz
        assert result.shape == (1, 16000)
        assert result.dtype == torch.float32


@pytest.mark.unit
class TestGstBufferConversion:
    """Test GStreamer buffer to tensor conversion."""

    def test_extract_audio_from_gst_buffer(self):
        """Test extracting audio from GstBuffer."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Mock GstBuffer
        mock_buffer = MagicMock()
        mock_memory = MagicMock()

        # Create fake audio data
        audio_data = np.random.randn(1600).astype(np.float32).tobytes()
        mock_memory.extract_dup.return_value = (True, audio_data)
        mock_buffer.get_all_memory.return_value = mock_memory
        mock_buffer.n_memory.return_value = 1

        # Mock caps
        mock_caps = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_int.side_effect = lambda x: (True, 16000) if x == "rate" else (True, 1)
        mock_structure.get_string.return_value = "F32LE"
        mock_caps.get_structure.return_value = mock_structure

        result = preprocessor.from_gst_buffer(mock_buffer, mock_caps)

        assert isinstance(result, torch.Tensor)
        assert result.shape[0] == 1  # Mono
        assert result.shape[1] == 1600  # Samples

    def test_handle_empty_buffer(self):
        """Test handling empty GstBuffer."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        mock_buffer = MagicMock()
        mock_buffer.n_memory.return_value = 0

        mock_caps = MagicMock()

        result = preprocessor.from_gst_buffer(mock_buffer, mock_caps)

        # Should return empty tensor
        assert result.numel() == 0


@pytest.mark.unit
class TestFormatNormalization:
    """Test audio format normalization."""

    def test_normalize_s16le_to_float(self):
        """Test normalizing S16LE to float32 [-1, 1]."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        # Max positive int16
        max_val = np.array([32767], dtype=np.int16)
        tensor = preprocessor.numpy_to_tensor(max_val, channels=1, format_str="S16LE")

        # Should be close to 1.0
        assert torch.allclose(tensor, torch.tensor([[1.0]]), atol=0.01)

        # Max negative int16
        min_val = np.array([-32768], dtype=np.int16)
        tensor = preprocessor.numpy_to_tensor(min_val, channels=1, format_str="S16LE")

        # Should be close to -1.0
        assert torch.allclose(tensor, torch.tensor([[-1.0]]), atol=0.01)

    def test_f32le_passthrough(self):
        """Test that F32LE passes through without modification."""
        from gst_pyannote.audio_preprocessor import AudioPreprocessor

        preprocessor = AudioPreprocessor()

        audio = np.array([0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        tensor = preprocessor.numpy_to_tensor(audio, channels=1, format_str="F32LE")

        expected = torch.tensor([[0.5, -0.5, 1.0, -1.0]])
        assert torch.allclose(tensor, expected)
