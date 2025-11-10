"""
JSON Output Handler

Formats speaker diarization results as JSON and emits them
on the GStreamer json_src pad.
"""

import json
from typing import Optional, Dict, Any

# Try to import GStreamer, but allow tests to mock it
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
except (ImportError, ValueError):
    Gst = None


class JSONOutputHandler:
    """
    Handles formatting and emission of diarization results as JSON.

    This class formats pyannote diarization results as JSON and creates
    GStreamer buffers that are pushed to the json_src pad.

    Can be used directly as a callback for InferenceWorker.

    Parameters
    ----------
    element : Gst.Element, optional
        GStreamer element (for accessing json_src pad)
    compact : bool, optional
        If True, produce compact JSON (no whitespace). Default: True
    jsonl_mode : bool, optional
        If True, produce line-delimited JSON (JSONL format). Default: False
    """

    def __init__(
        self,
        element: Optional[Any] = None,
        compact: bool = True,
        jsonl_mode: bool = False,
    ):
        self.element = element
        self.compact = compact
        self.jsonl_mode = jsonl_mode

    def format_json(self, results: Dict[str, Any]) -> str:
        """
        Format diarization results as JSON string.

        Parameters
        ----------
        results : dict
            Diarization results with keys:
            - events: List of speaker segments
            - speakers: List of unique speaker IDs
            - timestamp: Window start time

        Returns
        -------
        str
            JSON-formatted string
        """
        # Round timestamps for cleaner output
        formatted_events = []
        for event in results.get("events", []):
            formatted_events.append({
                "speaker": event["speaker"],
                "start": round(event["start"], 3),
                "end": round(event["end"], 3),
            })

        # Create output structure
        output = {
            "type": "diarization",
            "timestamp": results.get("timestamp", 0.0),
            "events": formatted_events,
            "speakers": results.get("speakers", []),
        }

        # Format based on mode
        if self.jsonl_mode:
            # JSONL: compact single line with trailing newline
            json_str = json.dumps(output, separators=(',', ':')) + '\n'
        elif self.compact:
            # Compact: no whitespace
            json_str = json.dumps(output, separators=(',', ':'))
        else:
            # Pretty: indented
            json_str = json.dumps(output, indent=2)

        return json_str

    def create_buffer(
        self,
        json_str: str,
        timestamp: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> Optional[Any]:
        """
        Create a GStreamer buffer containing JSON.

        Parameters
        ----------
        json_str : str
            JSON string to wrap in buffer
        timestamp : float, optional
            Timestamp in seconds (converted to nanoseconds for GStreamer)
        duration : float, optional
            Duration in seconds (converted to nanoseconds)

        Returns
        -------
        Gst.Buffer or None
            GStreamer buffer containing JSON bytes
        """
        if Gst is None:
            return None

        # Convert string to bytes
        json_bytes = json_str.encode('utf-8')

        # Create buffer
        buffer = Gst.Buffer.new_wrapped(json_bytes)

        # Set timestamps if provided
        if timestamp is not None:
            # Convert seconds to nanoseconds
            buffer.pts = int(timestamp * Gst.SECOND)

        if duration is not None:
            buffer.duration = int(duration * Gst.SECOND)

        return buffer

    def emit_results(self, results: Dict[str, Any]) -> Any:
        """
        Format results and emit on json_src pad.

        Parameters
        ----------
        results : dict
            Diarization results to emit

        Returns
        -------
        Gst.FlowReturn
            Result of pushing buffer (OK, ERROR, etc.)
        """
        if Gst is None or self.element is None:
            return Gst.FlowReturn.ERROR if Gst else None

        # Get json_src pad
        pad = self.element.get_static_pad("json_src")
        if pad is None:
            return Gst.FlowReturn.ERROR

        # Format JSON
        json_str = self.format_json(results)

        # Create buffer
        timestamp = results.get("timestamp", 0.0)
        buffer = self.create_buffer(json_str, timestamp=timestamp)

        if buffer is None:
            return Gst.FlowReturn.ERROR

        # Push buffer
        flow_return = pad.push(buffer)

        return flow_return

    def __call__(self, results: Dict[str, Any]) -> Any:
        """
        Make handler callable for use as InferenceWorker callback.

        Parameters
        ----------
        results : dict
            Diarization results

        Returns
        -------
        Gst.FlowReturn
            Result of emission
        """
        return self.emit_results(results)
