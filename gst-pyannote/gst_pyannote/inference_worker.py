"""
Inference Worker Thread

Background worker thread for running speaker diarization inference.
Decouples audio streaming from ML processing to avoid blocking.
"""

import torch
import threading
import queue
from typing import Optional, Callable, Any, Dict


class InferenceWorker:
    """
    Background thread for running pyannote inference.

    This worker runs in a separate thread and processes audio windows
    from a queue, allowing the main audio streaming thread to continue
    without blocking on inference.

    Parameters
    ----------
    pipeline_manager : PyannotePipelineManager
        Pipeline manager for running inference
    max_queue_size : int, optional
        Maximum number of queued audio windows (default: 10)
    on_result : callable, optional
        Callback function called with results: on_result(results_dict)
    on_error : callable, optional
        Callback function called on errors: on_error(exception, audio_info)
    """

    def __init__(
        self,
        pipeline_manager: Any,
        max_queue_size: int = 10,
        on_result: Optional[Callable[[Dict], None]] = None,
        on_error: Optional[Callable[[Exception, Any], None]] = None,
    ):
        self.pipeline_manager = pipeline_manager
        self.queue = queue.Queue(maxsize=max_queue_size)

        # Callbacks
        self.on_result = on_result
        self.on_error = on_error

        # Thread control
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Start the inference worker thread.

        The worker will run until stop() is called.
        """
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the inference worker thread.

        Parameters
        ----------
        timeout : float
            Maximum time to wait for thread to finish (seconds)
        """
        if not self.running:
            return

        self.running = False

        # Send poison pill to wake up thread
        try:
            self.queue.put(None, timeout=1.0)
        except queue.Full:
            pass

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)

    def submit_audio(
        self,
        audio_tensor: torch.Tensor,
        sample_rate: int,
        start_time: float,
        block: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Submit audio window for processing.

        Parameters
        ----------
        audio_tensor : torch.Tensor
            Audio as (1, num_samples) tensor
        sample_rate : int
            Audio sample rate
        start_time : float
            Start time of this window in the stream
        block : bool
            Whether to block if queue is full (default: True)
        timeout : float, optional
            Timeout for blocking (None = wait forever)

        Raises
        ------
        queue.Full
            If queue is full and block=False or timeout expires
        """
        item = (audio_tensor, sample_rate, start_time)

        if block:
            self.queue.put(item, timeout=timeout)
        else:
            self.queue.put_nowait(item)

    def _run(self) -> None:
        """
        Worker thread main loop.

        Continuously processes audio windows from the queue until stopped.
        """
        while self.running:
            try:
                # Wait for work with timeout so we can check running flag
                try:
                    item = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Check for poison pill (None = stop signal)
                if item is None:
                    break

                audio_tensor, sample_rate, start_time = item

                # Skip if pipeline not loaded
                if not self.pipeline_manager.is_loaded():
                    continue

                # Run inference
                try:
                    results = self.pipeline_manager.process_audio(
                        audio_tensor,
                        sample_rate,
                        start_time,
                    )

                    # Call result callback if provided
                    if self.on_result is not None:
                        self.on_result(results)

                except Exception as e:
                    # Call error callback if provided
                    if self.on_error is not None:
                        self.on_error(e, (audio_tensor, sample_rate, start_time))
                    # Continue processing even after errors

            except Exception as e:
                # Catch any unexpected exceptions to keep thread alive
                if self.on_error is not None:
                    self.on_error(e, None)

    def get_queue_size(self) -> int:
        """
        Get current number of items in the queue.

        Returns
        -------
        int
            Number of queued audio windows
        """
        return self.queue.qsize()

    def clear_queue(self) -> None:
        """
        Clear all pending items from the queue.

        This discards any audio windows waiting for processing.
        """
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def is_busy(self) -> bool:
        """
        Check if worker is busy (has queued work).

        Returns
        -------
        bool
            True if there are items in the queue
        """
        return not self.queue.empty()
