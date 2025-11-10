"""
Audio Preprocessing for GStreamer Buffers

Handles conversion from GStreamer buffers to PyTorch tensors,
including format conversion, resampling, and channel mixing.
"""

import torch
import torchaudio
import numpy as np
from typing import Optional, Dict


class AudioPreprocessor:
    """
    Audio preprocessing pipeline for GStreamer buffers.

    Handles:
    - GstBuffer to PyTorch tensor conversion
    - Format conversion (S16LE, F32LE, etc.)
    - Sample rate conversion
    - Channel downmixing (stereo to mono)

    Parameters
    ----------
    target_rate : int
        Target sample rate for output audio
    """

    def __init__(self, target_rate: int = 16000):
        self.target_rate = target_rate
        self._resamplers: Dict[int, torchaudio.transforms.Resample] = {}

    def numpy_to_tensor(
        self,
        audio_np: np.ndarray,
        channels: int,
        format_str: str = "F32LE",
    ) -> torch.Tensor:
        """
        Convert NumPy array to PyTorch tensor.

        Parameters
        ----------
        audio_np : np.ndarray
            Raw audio data as numpy array
        channels : int
            Number of audio channels
        format_str : str
            Audio format (F32LE, S16LE, etc.)

        Returns
        -------
        torch.Tensor
            Audio as (channels, samples) tensor
        """
        # Convert based on format
        if format_str == "S16LE":
            # Convert int16 to float32 [-1, 1]
            audio_float = audio_np.astype(np.float32) / 32768.0
        elif format_str == "F32LE":
            # Already float32
            audio_float = audio_np.astype(np.float32)
        else:
            raise ValueError(f"Unsupported format: {format_str}")

        # Convert to tensor
        tensor = torch.from_numpy(audio_float)

        # Deinterleave channels if multi-channel
        if channels > 1:
            # Reshape from interleaved to (channels, samples)
            num_samples = len(tensor) // channels
            tensor = tensor.reshape(num_samples, channels).T
        else:
            # Add channel dimension
            tensor = tensor.unsqueeze(0)

        return tensor

    def stereo_to_mono(self, audio: torch.Tensor) -> torch.Tensor:
        """
        Convert multi-channel audio to mono by averaging.

        Parameters
        ----------
        audio : torch.Tensor
            Audio as (channels, samples) tensor

        Returns
        -------
        torch.Tensor
            Mono audio as (1, samples) tensor
        """
        if audio.shape[0] == 1:
            # Already mono
            return audio

        # Average all channels
        return audio.mean(dim=0, keepdim=True)

    def resample(
        self,
        audio: torch.Tensor,
        source_rate: int,
    ) -> torch.Tensor:
        """
        Resample audio to target sample rate.

        Parameters
        ----------
        audio : torch.Tensor
            Audio as (channels, samples) tensor
        source_rate : int
            Source sample rate

        Returns
        -------
        torch.Tensor
            Resampled audio
        """
        if source_rate == self.target_rate:
            # No resampling needed
            return audio

        # Get or create resampler for this rate
        if source_rate not in self._resamplers:
            self._resamplers[source_rate] = torchaudio.transforms.Resample(
                orig_freq=source_rate,
                new_freq=self.target_rate,
            )

        resampler = self._resamplers[source_rate]
        return resampler(audio)

    def process(
        self,
        audio_np: np.ndarray,
        source_rate: int,
        channels: int,
        format_str: str = "F32LE",
        to_mono: bool = True,
    ) -> torch.Tensor:
        """
        Full preprocessing pipeline.

        Parameters
        ----------
        audio_np : np.ndarray
            Raw audio data
        source_rate : int
            Source sample rate
        channels : int
            Number of channels
        format_str : str
            Audio format
        to_mono : bool
            Whether to downmix to mono

        Returns
        -------
        torch.Tensor
            Preprocessed audio as (channels, samples) tensor
        """
        # Convert to tensor
        audio = self.numpy_to_tensor(audio_np, channels, format_str)

        # Downmix to mono if requested
        if to_mono and audio.shape[0] > 1:
            audio = self.stereo_to_mono(audio)

        # Resample if needed
        if source_rate != self.target_rate:
            audio = self.resample(audio, source_rate)

        return audio

    def from_gst_buffer(self, buffer, caps) -> torch.Tensor:
        """
        Extract audio from GstBuffer.

        Parameters
        ----------
        buffer : Gst.Buffer
            GStreamer buffer containing audio
        caps : Gst.Caps
            Capabilities describing the audio format

        Returns
        -------
        torch.Tensor
            Audio as (channels, samples) tensor
        """
        # Check if buffer has data
        if buffer.n_memory() == 0:
            return torch.empty(1, 0)

        # Extract binary data from buffer
        memory = buffer.get_all_memory()
        success, data = memory.extract_dup(0, memory.get_size())

        if not success:
            return torch.empty(1, 0)

        # Parse caps to get format info
        structure = caps.get_structure(0)
        success_rate, sample_rate = structure.get_int("rate")
        success_channels, channels = structure.get_int("channels")
        format_str = structure.get_string("format")

        if not (success_rate and success_channels):
            return torch.empty(1, 0)

        # Convert bytes to numpy array based on format
        if format_str == "F32LE":
            audio_np = np.frombuffer(data, dtype=np.float32)
        elif format_str == "S16LE":
            audio_np = np.frombuffer(data, dtype=np.int16)
        else:
            raise ValueError(f"Unsupported format: {format_str}")

        # Process
        return self.process(
            audio_np,
            source_rate=sample_rate,
            channels=channels,
            format_str=format_str,
            to_mono=True,
        )
