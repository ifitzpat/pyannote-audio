"""
Phase 3 Tests: Inference Worker Thread

Tests for the InferenceWorker class that handles:
- Background thread for running inference
- Queue-based audio window submission
- Result callbacks
- Error handling
- Thread lifecycle management
"""

import pytest
import torch
import time
import queue
from unittest.mock import MagicMock, patch, call


@pytest.mark.unit
class TestInferenceWorkerInit:
    """Test InferenceWorker initialization."""

    def test_worker_can_be_created(self):
        """Test that InferenceWorker can be instantiated."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        assert worker is not None

    def test_worker_stores_pipeline_manager(self):
        """Test worker stores pipeline manager reference."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        assert worker.pipeline_manager is mock_pipeline_manager

    def test_worker_has_queue(self):
        """Test worker has a queue for audio windows."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        assert hasattr(worker, "queue")
        assert isinstance(worker.queue, queue.Queue)

    def test_worker_starts_as_not_running(self):
        """Test worker starts in not running state."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        assert worker.running is False

    def test_worker_queue_size_configurable(self):
        """Test queue size can be configured."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager, max_queue_size=5)

        assert worker.queue.maxsize == 5


@pytest.mark.unit
class TestWorkerCallbacks:
    """Test callback registration."""

    def test_worker_accepts_result_callback(self):
        """Test worker can register result callback."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_callback = MagicMock()

        worker = InferenceWorker(
            mock_pipeline_manager,
            on_result=mock_callback
        )

        assert worker.on_result is mock_callback

    def test_worker_accepts_error_callback(self):
        """Test worker can register error callback."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_error_callback = MagicMock()

        worker = InferenceWorker(
            mock_pipeline_manager,
            on_error=mock_error_callback
        )

        assert worker.on_error is mock_error_callback

    def test_worker_callbacks_optional(self):
        """Test callbacks are optional."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        # Should not raise
        assert worker.on_result is None or callable(worker.on_result)
        assert worker.on_error is None or callable(worker.on_error)


@pytest.mark.unit
class TestAudioSubmission:
    """Test submitting audio for processing."""

    def test_submit_audio_adds_to_queue(self):
        """Test submit_audio adds work to queue."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 0.0)

        assert worker.queue.qsize() == 1

    def test_submit_audio_stores_all_parameters(self):
        """Test submit stores audio, sample_rate, and start_time."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 5.0)

        item = worker.queue.get(block=False)
        assert len(item) == 3
        assert torch.allclose(item[0], audio)
        assert item[1] == 16000
        assert item[2] == 5.0

    def test_submit_audio_blocks_when_queue_full(self):
        """Test submit blocks when queue is full."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager, max_queue_size=1)

        audio1 = torch.randn(1, 16000)
        audio2 = torch.randn(1, 16000)

        # First submit succeeds
        worker.submit_audio(audio1, 16000, 0.0)

        # Second should succeed with nowait flag (raises if would block)
        with pytest.raises(queue.Full):
            worker.submit_audio(audio2, 16000, 1.0, block=False)

    def test_submit_audio_with_timeout(self):
        """Test submit with timeout."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager, max_queue_size=1)

        audio1 = torch.randn(1, 16000)
        audio2 = torch.randn(1, 16000)

        worker.submit_audio(audio1, 16000, 0.0)

        # Should timeout trying to add second
        with pytest.raises(queue.Full):
            worker.submit_audio(audio2, 16000, 1.0, timeout=0.1)


@pytest.mark.unit
class TestWorkerLifecycle:
    """Test worker start/stop lifecycle."""

    def test_start_sets_running_flag(self):
        """Test start() sets running flag."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        worker.start()

        assert worker.running is True

        # Clean up
        worker.stop()

    def test_start_creates_thread(self):
        """Test start() creates and starts thread."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        worker.start()

        assert hasattr(worker, "thread")
        assert worker.thread.is_alive()

        # Clean up
        worker.stop()

    def test_stop_clears_running_flag(self):
        """Test stop() clears running flag."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        worker.start()
        worker.stop()

        assert worker.running is False

    def test_stop_joins_thread(self):
        """Test stop() waits for thread to finish."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = True
        mock_pipeline_manager.process_audio.return_value = {
            "events": [],
            "speakers": [],
        }

        worker = InferenceWorker(mock_pipeline_manager)
        worker.start()

        # Add some work
        worker.submit_audio(torch.randn(1, 16000), 16000, 0.0)

        # Give thread time to start
        time.sleep(0.1)

        worker.stop()

        # Thread should be stopped
        assert not worker.thread.is_alive()

    def test_stop_when_not_started(self):
        """Test stop() is safe when worker not started."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        # Should not raise
        worker.stop()


@pytest.mark.unit
class TestInferenceProcessing:
    """Test actual inference processing."""

    def test_worker_processes_submitted_audio(self):
        """Test worker processes audio from queue."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = True
        mock_pipeline_manager.process_audio.return_value = {
            "events": [],
            "speakers": [],
        }

        worker = InferenceWorker(mock_pipeline_manager)
        worker.start()

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 0.0)

        # Give thread time to process
        time.sleep(0.2)

        worker.stop()

        # Pipeline should have been called
        mock_pipeline_manager.process_audio.assert_called_once()

    def test_worker_calls_result_callback(self):
        """Test worker calls result callback with results."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = True
        mock_result = {"events": [], "speakers": []}
        mock_pipeline_manager.process_audio.return_value = mock_result

        mock_callback = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager, on_result=mock_callback)
        worker.start()

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 0.0)

        time.sleep(0.2)
        worker.stop()

        # Callback should have been called with results
        mock_callback.assert_called_once_with(mock_result)

    def test_worker_skips_if_no_pipeline_loaded(self):
        """Test worker skips processing if pipeline not loaded."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = False

        worker = InferenceWorker(mock_pipeline_manager)
        worker.start()

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 0.0)

        time.sleep(0.2)
        worker.stop()

        # Should not call process_audio
        mock_pipeline_manager.process_audio.assert_not_called()


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in worker."""

    def test_worker_catches_processing_errors(self):
        """Test worker catches exceptions during processing."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = True
        mock_pipeline_manager.process_audio.side_effect = Exception("Processing failed")

        worker = InferenceWorker(mock_pipeline_manager)
        worker.start()

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 0.0)

        time.sleep(0.2)

        # Worker should still be running
        assert worker.running

        worker.stop()

    def test_worker_calls_error_callback_on_exception(self):
        """Test worker calls error callback when exception occurs."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = True
        mock_pipeline_manager.process_audio.side_effect = Exception("Processing failed")

        mock_error_callback = MagicMock()
        worker = InferenceWorker(
            mock_pipeline_manager,
            on_error=mock_error_callback
        )
        worker.start()

        audio = torch.randn(1, 16000)
        worker.submit_audio(audio, 16000, 0.0)

        time.sleep(0.2)
        worker.stop()

        # Error callback should have been called
        mock_error_callback.assert_called_once()

    def test_worker_continues_after_error(self):
        """Test worker continues processing after an error."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        mock_pipeline_manager.is_loaded.return_value = True

        # First call fails, second succeeds
        mock_pipeline_manager.process_audio.side_effect = [
            Exception("First failed"),
            {"events": [], "speakers": []},
        ]

        worker = InferenceWorker(mock_pipeline_manager)
        worker.start()

        # Submit two audio windows
        audio1 = torch.randn(1, 16000)
        audio2 = torch.randn(1, 16000)
        worker.submit_audio(audio1, 16000, 0.0)
        worker.submit_audio(audio2, 16000, 1.0)

        time.sleep(0.3)
        worker.stop()

        # Should have called process_audio twice
        assert mock_pipeline_manager.process_audio.call_count == 2


@pytest.mark.unit
class TestQueueManagement:
    """Test queue management features."""

    def test_get_queue_size(self):
        """Test getting current queue size."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        assert worker.get_queue_size() == 0

        worker.submit_audio(torch.randn(1, 16000), 16000, 0.0)
        assert worker.get_queue_size() == 1

    def test_clear_queue(self):
        """Test clearing the queue."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        # Add multiple items
        for i in range(3):
            worker.submit_audio(torch.randn(1, 16000), 16000, float(i))

        assert worker.get_queue_size() == 3

        worker.clear_queue()

        assert worker.get_queue_size() == 0

    def test_is_busy(self):
        """Test checking if worker is busy."""
        from gst_pyannote.inference_worker import InferenceWorker

        mock_pipeline_manager = MagicMock()
        worker = InferenceWorker(mock_pipeline_manager)

        # Not started, not busy
        assert worker.is_busy() is False

        worker.start()

        # Started but no work
        assert worker.is_busy() is False

        worker.submit_audio(torch.randn(1, 16000), 16000, 0.0)

        # Has work queued
        assert worker.is_busy() is True

        worker.stop()
