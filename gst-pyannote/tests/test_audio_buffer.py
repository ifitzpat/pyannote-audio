"""
Phase 2 Tests: Audio Buffering System

Tests for the AudioRingBuffer class that accumulates audio chunks
and creates overlapping windows for processing.
"""

import pytest
import torch
import numpy as np


@pytest.mark.unit
class TestAudioRingBufferInit:
    """Test AudioRingBuffer initialization."""

    def test_buffer_can_be_created(self):
        """Test that AudioRingBuffer can be instantiated."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=30.0,
            overlap_duration=5.0,
            sample_rate=16000
        )
        assert buffer is not None

    def test_buffer_calculates_window_size(self):
        """Test buffer correctly calculates window size in samples."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=10.0,
            overlap_duration=2.0,
            sample_rate=16000
        )

        expected_window_samples = 10.0 * 16000  # 160,000 samples
        assert buffer.window_samples == expected_window_samples

    def test_buffer_calculates_overlap_size(self):
        """Test buffer correctly calculates overlap size."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=30.0,
            overlap_duration=5.0,
            sample_rate=16000
        )

        expected_overlap_samples = 5.0 * 16000  # 80,000 samples
        assert buffer.overlap_samples == expected_overlap_samples

    def test_buffer_calculates_step_size(self):
        """Test buffer calculates step size (window - overlap)."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=30.0,
            overlap_duration=5.0,
            sample_rate=16000
        )

        expected_step = (30.0 - 5.0) * 16000  # 25 seconds = 400,000 samples
        assert buffer.step_samples == expected_step

    def test_buffer_initializes_empty(self):
        """Test buffer starts with no audio."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer()
        assert buffer.num_samples == 0


@pytest.mark.unit
class TestAudioRingBufferPush:
    """Test pushing audio into the buffer."""

    def test_push_audio_increases_sample_count(self):
        """Test that pushing audio increases the sample count."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(window_duration=10.0, sample_rate=16000)

        # Push 1 second of audio
        audio_chunk = torch.randn(1, 16000)
        buffer.push(audio_chunk)

        assert buffer.num_samples == 16000

    def test_push_returns_none_when_not_ready(self):
        """Test push returns None when window not filled."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(window_duration=10.0, sample_rate=16000)

        # Push only 1 second (need 10 seconds for full window)
        audio_chunk = torch.randn(1, 16000)
        result = buffer.push(audio_chunk)

        assert result is None

    def test_push_returns_window_when_ready(self):
        """Test push returns window when enough audio accumulated."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=1.0,
            overlap_duration=0.0,
            sample_rate=16000
        )

        # Push exactly 1 second
        audio_chunk = torch.randn(1, 16000)
        result = buffer.push(audio_chunk)

        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 3  # (audio_window, start_time, end_time)

    def test_push_multiple_chunks(self):
        """Test pushing multiple small chunks."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=1.0,
            overlap_duration=0.0,
            sample_rate=16000
        )

        # Push 10 chunks of 0.1 seconds each
        for _ in range(10):
            chunk = torch.randn(1, 1600)  # 0.1s at 16kHz
            buffer.push(chunk)

        # Now should have exactly 1 second
        assert buffer.num_samples == 16000

    def test_returned_window_has_correct_shape(self):
        """Test returned window has shape (1, window_samples)."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=2.0,
            overlap_duration=0.0,
            sample_rate=16000
        )

        audio_chunk = torch.randn(1, 32000)  # 2 seconds
        result = buffer.push(audio_chunk)

        audio_window, start_time, end_time = result
        assert audio_window.shape == (1, 32000)

    def test_window_timestamps_are_correct(self):
        """Test returned window has correct start/end timestamps."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=1.0,
            overlap_duration=0.0,
            sample_rate=16000
        )

        # Push first window
        chunk1 = torch.randn(1, 16000)
        result1 = buffer.push(chunk1)
        audio1, start1, end1 = result1

        assert start1 == 0.0
        assert end1 == 1.0

        # Push second window
        chunk2 = torch.randn(1, 16000)
        result2 = buffer.push(chunk2)
        audio2, start2, end2 = result2

        assert start2 == 1.0
        assert end2 == 2.0


@pytest.mark.unit
class TestAudioRingBufferOverlap:
    """Test overlapping window behavior."""

    def test_overlap_creates_sliding_windows(self):
        """Test that overlap creates properly sliding windows."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=2.0,
            overlap_duration=1.0,  # 50% overlap
            sample_rate=16000
        )

        # Push first 2 seconds
        chunk1 = torch.randn(1, 32000)
        result1 = buffer.push(chunk1)
        assert result1 is not None

        # Push next 1 second (should trigger next window due to overlap)
        chunk2 = torch.randn(1, 16000)
        result2 = buffer.push(chunk2)
        assert result2 is not None

        # Windows should overlap
        audio1, start1, end1 = result1
        audio2, start2, end2 = result2

        # Second window starts 1 second after first (step = window - overlap)
        assert start2 == start1 + 1.0

    def test_overlap_window_contains_previous_data(self):
        """Test that overlapping windows share data."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=2.0,
            overlap_duration=1.0,
            sample_rate=16000
        )

        # Create identifiable audio pattern
        chunk1 = torch.ones(1, 32000) * 1.0  # First 2 seconds: all 1.0
        result1 = buffer.push(chunk1)

        chunk2 = torch.ones(1, 16000) * 2.0  # Next 1 second: all 2.0
        result2 = buffer.push(chunk2)

        audio2, _, _ = result2

        # Second window should have:
        # - First 1 second (overlap): from first window (value 1.0)
        # - Last 1 second: from second chunk (value 2.0)
        assert torch.allclose(audio2[0, :16000], torch.ones(16000) * 1.0)
        assert torch.allclose(audio2[0, 16000:], torch.ones(16000) * 2.0)


@pytest.mark.unit
class TestAudioRingBufferReset:
    """Test buffer reset functionality."""

    def test_reset_clears_buffer(self):
        """Test that reset clears accumulated audio."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(window_duration=10.0, sample_rate=16000)

        # Add some audio
        buffer.push(torch.randn(1, 16000))
        assert buffer.num_samples > 0

        # Reset
        buffer.reset()
        assert buffer.num_samples == 0

    def test_reset_resets_timestamps(self):
        """Test that reset resets stream time tracking."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(
            window_duration=1.0,
            overlap_duration=0.0,
            sample_rate=16000
        )

        # Process some windows
        buffer.push(torch.randn(1, 16000))
        buffer.push(torch.randn(1, 16000))

        buffer.reset()

        # Next window should start at 0
        result = buffer.push(torch.randn(1, 16000))
        if result:
            _, start, _ = result
            assert start == 0.0


@pytest.mark.unit
class TestAudioRingBufferProperties:
    """Test buffer properties and state queries."""

    def test_is_ready_property(self):
        """Test is_ready property indicates if window is ready."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(window_duration=1.0, sample_rate=16000)

        assert not buffer.is_ready

        buffer.push(torch.randn(1, 16000))

        assert buffer.is_ready

    def test_get_duration_property(self):
        """Test duration property returns current duration in seconds."""
        from gst_pyannote.audio_buffer import AudioRingBuffer

        buffer = AudioRingBuffer(sample_rate=16000)

        assert buffer.duration == 0.0

        buffer.push(torch.randn(1, 16000))  # 1 second

        assert buffer.duration == 1.0

        buffer.push(torch.randn(1, 8000))  # 0.5 seconds

        assert buffer.duration == 1.5
