"""
Pyannote Pipeline Manager

Manages pyannote-audio pipeline lifecycle:
- Loading models from Hugging Face
- Running speaker diarization inference
- Thread-safe operations
- Resource cleanup
"""

import torch
import threading
from typing import Optional, Dict, Any

# Import will fail if pyannote.audio not installed, but tests can mock it
try:
    from pyannote.audio import Pipeline
except ImportError:
    Pipeline = None


class PyannotePipelineManager:
    """
    Manages pyannote pipeline lifecycle and inference.

    This class handles loading/unloading pyannote models and running
    speaker diarization inference in a thread-safe manner.

    Parameters
    ----------
    device : str, optional
        PyTorch device to use ("cuda", "cpu", etc.)
        If None, automatically detects CUDA availability
    """

    def __init__(self, device: Optional[str] = None):
        # Determine device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        # Pipeline state
        self.pipeline: Optional[Any] = None  # Pipeline instance
        self.model_name: Optional[str] = None

        # Thread safety
        self.lock = threading.Lock()

        # Pipeline parameters (can be updated at runtime)
        self.params = {
            "min_speakers": None,  # None = auto
            "max_speakers": None,  # None = auto
            "segmentation_step": 0.1,
            "embedding_batch_size": 32,
            "clustering": "AgglomerativeClustering",
        }

    def load_pipeline(
        self,
        model_name: str,
        use_auth_token: Optional[str] = None,
    ) -> None:
        """
        Load a pyannote pipeline from Hugging Face.

        Parameters
        ----------
        model_name : str
            Hugging Face model identifier (e.g., "pyannote/speaker-diarization-3.1")
        use_auth_token : str, optional
            Hugging Face authentication token for gated models

        Raises
        ------
        Exception
            If model loading fails
        """
        with self.lock:
            if Pipeline is None:
                raise ImportError(
                    "pyannote.audio is not installed. "
                    "Install with: pip install pyannote-audio"
                )

            # Load pipeline from Hugging Face
            self.pipeline = Pipeline.from_pretrained(
                model_name,
                use_auth_token=use_auth_token,
            )

            # Move to device
            self.pipeline.to(self.device)

            self.model_name = model_name

    def unload_pipeline(self) -> None:
        """
        Unload the pipeline and free resources.

        This moves the model to CPU and clears GPU cache to free memory.
        """
        with self.lock:
            if self.pipeline is not None:
                # Move to CPU to free GPU memory
                self.pipeline.to(torch.device("cpu"))

                # Clear references
                self.pipeline = None
                self.model_name = None

                # Force GPU cleanup
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    def update_parameters(self, params: Dict[str, Any]) -> None:
        """
        Update pipeline parameters.

        Parameters
        ----------
        params : dict
            Parameters to update (e.g., {"min_speakers": 2, "max_speakers": 10})
        """
        self.params.update(params)

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current pipeline parameters.

        Returns
        -------
        dict
            Current parameters
        """
        return self.params.copy()

    def process_audio(
        self,
        audio_tensor: torch.Tensor,
        sample_rate: int,
        start_time: float,
    ) -> Dict[str, Any]:
        """
        Run speaker diarization on an audio window.

        Parameters
        ----------
        audio_tensor : torch.Tensor
            Audio as (1, num_samples) tensor
        sample_rate : int
            Audio sample rate
        start_time : float
            Start time of this window in the stream (for timestamp adjustment)

        Returns
        -------
        dict
            Diarization results with format:
            {
                "events": [
                    {"speaker": "SPEAKER_00", "start": 1.0, "end": 3.0},
                    ...
                ],
                "speakers": ["SPEAKER_00", "SPEAKER_01", ...],
                "timestamp": <window_start_time>,
            }

        Raises
        ------
        RuntimeError
            If no pipeline is loaded
        """
        with self.lock:
            if self.pipeline is None:
                raise RuntimeError("No pipeline loaded")

            # Create audio dict for pyannote
            audio_dict = {
                "waveform": audio_tensor,
                "sample_rate": sample_rate,
            }

            # Run diarization with parameters
            diarization = self.pipeline(
                audio_dict,
                min_speakers=self.params["min_speakers"],
                max_speakers=self.params["max_speakers"],
            )

            # Format results
            results = self._format_results(diarization, start_time)

            return results

    def _format_results(self, diarization: Any, start_time: float) -> Dict[str, Any]:
        """
        Format pyannote diarization output to JSON-serializable dict.

        Parameters
        ----------
        diarization : Annotation
            Pyannote Annotation object
        start_time : float
            Offset to add to all timestamps

        Returns
        -------
        dict
            Formatted results
        """
        events = []

        # Extract all speaker segments
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            events.append({
                "speaker": speaker,
                "start": segment.start + start_time,
                "end": segment.end + start_time,
            })

        # Get list of unique speakers
        speakers = list(diarization.labels())

        return {
            "events": events,
            "speakers": speakers,
            "timestamp": start_time,
        }

    def is_loaded(self) -> bool:
        """
        Check if a pipeline is currently loaded.

        Returns
        -------
        bool
            True if pipeline is loaded
        """
        return self.pipeline is not None
