"""
Audio Ring Buffer for Sliding Window Processing

Accumulates audio chunks and creates overlapping windows for
speaker diarization inference.
"""

import torch
from typing import Optional, Tuple


class AudioRingBuffer:
    """
    Circular buffer for audio accumulation with overlapping window support.

    This buffer accumulates incoming audio and emits windows when enough
    audio has been collected. Windows overlap to ensure smooth transitions
    in diarization output.

    Parameters
    ----------
    window_duration : float
        Duration of each processing window in seconds
    overlap_duration : float
        Overlap between consecutive windows in seconds
    sample_rate : int
        Audio sample rate in Hz
    """

    def __init__(
        self,
        window_duration: float = 30.0,
        overlap_duration: float = 5.0,
        sample_rate: int = 16000,
    ):
        self.window_duration = window_duration
        self.overlap_duration = overlap_duration
        self.sample_rate = sample_rate

        # Calculate sizes in samples
        self.window_samples = int(window_duration * sample_rate)
        self.overlap_samples = int(overlap_duration * sample_rate)
        self.step_samples = self.window_samples - self.overlap_samples

        # Buffer to hold audio (allocate double the window size for safety)
        self.buffer = torch.zeros(1, self.window_samples * 2, dtype=torch.float32)

        # Current position in buffer
        self.num_samples = 0

        # Stream time tracking
        self.stream_time = 0.0

        # How many windows we've emitted
        self.windows_emitted = 0

    def push(
        self, audio_chunk: torch.Tensor
    ) -> Optional[Tuple[torch.Tensor, float, float]]:
        """
        Push audio into the buffer.

        Parameters
        ----------
        audio_chunk : torch.Tensor
            Audio chunk as (channels, samples) tensor

        Returns
        -------
        tuple or None
            If a window is ready: (audio_window, start_time, end_time)
            Otherwise: None
        """
        chunk_samples = audio_chunk.shape[1]

        # Ensure we have space in buffer
        if self.num_samples + chunk_samples > self.buffer.shape[1]:
            # Expand buffer
            new_size = (self.num_samples + chunk_samples) * 2
            new_buffer = torch.zeros(1, new_size, dtype=torch.float32)
            new_buffer[:, : self.num_samples] = self.buffer[:, : self.num_samples]
            self.buffer = new_buffer

        # Add chunk to buffer (assume mono - take first channel if multi-channel)
        if audio_chunk.shape[0] > 1:
            audio_chunk = audio_chunk.mean(dim=0, keepdim=True)

        self.buffer[:, self.num_samples : self.num_samples + chunk_samples] = audio_chunk
        self.num_samples += chunk_samples

        # Check if we have enough for a window
        if self.num_samples >= self.window_samples:
            # Extract window
            start_idx = self.windows_emitted * self.step_samples
            end_idx = start_idx + self.window_samples

            if end_idx <= self.num_samples:
                window = self.buffer[:, start_idx:end_idx].clone()

                # Calculate timestamps
                start_time = start_idx / self.sample_rate
                end_time = end_idx / self.sample_rate

                self.windows_emitted += 1

                return (window, start_time, end_time)

        return None

    def reset(self):
        """Reset the buffer to empty state."""
        self.buffer.zero_()
        self.num_samples = 0
        self.stream_time = 0.0
        self.windows_emitted = 0

    @property
    def is_ready(self) -> bool:
        """Check if buffer has enough audio for a window."""
        return self.num_samples >= self.window_samples

    @property
    def duration(self) -> float:
        """Get current buffer duration in seconds."""
        return self.num_samples / self.sample_rate
