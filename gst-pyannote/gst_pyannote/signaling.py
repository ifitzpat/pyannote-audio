"""
Signaling System

Provides event signaling for the GstPyannote element using:
- GObject signals for application integration
- GStreamer custom events for pipeline communication
- Bus messages for element state notifications
"""

from typing import Optional, Dict, Any, Callable, List
from collections import defaultdict

# Try to import GStreamer, but allow tests to mock it
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib
except (ImportError, ValueError):
    Gst = None
    GLib = None


class SignalManager:
    """
    Manages signal emission for the GstPyannote element.

    Provides a unified interface for emitting signals as:
    - GStreamer custom events
    - GStreamer bus messages
    - Python callbacks

    Parameters
    ----------
    element : Gst.Element, optional
        GStreamer element for signal emission
    """

    def __init__(self, element: Optional[Any] = None):
        self.element = element

        # Signal definitions
        self.signals = {
            "model-loaded": "Emitted when a model is loaded",
            "model-unloaded": "Emitted when a model is unloaded",
            "inference-started": "Emitted when inference starts on a window",
            "inference-complete": "Emitted when inference completes",
            "speaker-detected": "Emitted when a speaker segment is detected",
            "parameter-changed": "Emitted when a parameter changes",
            "error-occurred": "Emitted when an error occurs",
        }

        # Callback registry: signal_name -> [callbacks]
        self.callbacks = defaultdict(list)

    def register_callback(
        self,
        signal_name: str,
        callback: Callable,
    ) -> None:
        """
        Register a callback for a signal.

        Parameters
        ----------
        signal_name : str
            Name of the signal to listen for
        callback : callable
            Function to call when signal is emitted
        """
        if signal_name not in self.signals:
            raise ValueError(f"Unknown signal: {signal_name}")

        self.callbacks[signal_name].append(callback)

    def unregister_callback(
        self,
        signal_name: str,
        callback: Callable,
    ) -> None:
        """
        Unregister a callback for a signal.

        Parameters
        ----------
        signal_name : str
            Name of the signal
        callback : callable
            Callback to remove
        """
        if signal_name in self.callbacks:
            if callback in self.callbacks[signal_name]:
                self.callbacks[signal_name].remove(callback)

    def _invoke_callbacks(self, signal_name: str, *args, **kwargs) -> None:
        """
        Invoke all registered callbacks for a signal.

        Parameters
        ----------
        signal_name : str
            Signal name
        *args, **kwargs
            Arguments to pass to callbacks
        """
        for callback in self.callbacks.get(signal_name, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                # Don't let callback errors break signal emission
                pass

    def emit_model_loaded(self, model_name: str) -> None:
        """
        Emit model-loaded signal.

        Parameters
        ----------
        model_name : str
            Name of the loaded model
        """
        data = self.format_model_loaded_data(model_name)

        # Invoke callbacks
        self._invoke_callbacks("model-loaded", model_name)

        # Post bus message
        self.post_element_message("pyannote-model-loaded", data)

        # Send custom event
        self.send_event_downstream("pyannote-model-loaded", data)

    def emit_model_unloaded(self) -> None:
        """
        Emit model-unloaded signal.
        """
        # Invoke callbacks
        self._invoke_callbacks("model-unloaded")

        # Post bus message
        self.post_element_message("pyannote-model-unloaded", {})

        # Send custom event
        self.send_event_downstream("pyannote-model-unloaded", {})

    def emit_inference_started(self, timestamp: float) -> None:
        """
        Emit inference-started signal.

        Parameters
        ----------
        timestamp : float
            Start timestamp of the window
        """
        data = {"timestamp": timestamp}

        # Invoke callbacks
        self._invoke_callbacks("inference-started", timestamp)

        # Send custom event
        self.send_event_downstream("pyannote-inference-started", data)

    def emit_inference_complete(self, results: Dict[str, Any]) -> None:
        """
        Emit inference-complete signal.

        Parameters
        ----------
        results : dict
            Diarization results
        """
        data = self.format_inference_complete_data(results)

        # Invoke callbacks
        self._invoke_callbacks("inference-complete", results)

        # Post bus message
        self.post_element_message("pyannote-inference-complete", data)

        # Send custom event
        self.send_event_downstream("pyannote-inference-complete", data)

    def emit_speaker_detected(
        self,
        speaker_id: str,
        start_time: float,
        end_time: float,
    ) -> None:
        """
        Emit speaker-detected signal.

        Parameters
        ----------
        speaker_id : str
            Speaker identifier
        start_time : float
            Segment start time
        end_time : float
            Segment end time
        """
        data = self.format_speaker_detected_data(speaker_id, start_time, end_time)

        # Invoke callbacks
        self._invoke_callbacks("speaker-detected", speaker_id, start_time, end_time)

        # Send custom event
        self.send_event_downstream("pyannote-speaker-detected", data)

    def emit_parameter_changed(
        self,
        parameter_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """
        Emit parameter-changed signal.

        Parameters
        ----------
        parameter_name : str
            Name of the parameter
        old_value : any
            Previous value
        new_value : any
            New value
        """
        data = {
            "parameter": parameter_name,
            "old_value": str(old_value),
            "new_value": str(new_value),
        }

        # Invoke callbacks
        self._invoke_callbacks("parameter-changed", parameter_name, old_value, new_value)

        # Post bus message
        self.post_element_message("pyannote-parameter-changed", data)

        # Send custom event
        self.send_event_downstream("pyannote-parameter-changed", data)

    def emit_error_occurred(
        self,
        error_message: str,
        error_type: str = "Error",
    ) -> None:
        """
        Emit error-occurred signal.

        Parameters
        ----------
        error_message : str
            Error description
        error_type : str
            Type of error
        """
        data = self.format_error_data(error_message, error_type)

        # Invoke callbacks
        self._invoke_callbacks("error-occurred", error_message, error_type)

        # Post error message to bus
        self._post_error_message(error_message, error_type)

        # Send custom event
        self.send_event_downstream("pyannote-error", data)

    def format_model_loaded_data(self, model_name: str) -> Dict[str, Any]:
        """
        Format model-loaded signal data.

        Parameters
        ----------
        model_name : str
            Model name

        Returns
        -------
        dict
            Formatted signal data
        """
        return {
            "model_name": model_name,
        }

    def format_inference_complete_data(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format inference-complete signal data.

        Parameters
        ----------
        results : dict
            Diarization results

        Returns
        -------
        dict
            Formatted signal data
        """
        return {
            "timestamp": results.get("timestamp", 0.0),
            "speaker_count": len(results.get("speakers", [])),
            "event_count": len(results.get("events", [])),
        }

    def format_speaker_detected_data(
        self,
        speaker_id: str,
        start: float,
        end: float,
    ) -> Dict[str, Any]:
        """
        Format speaker-detected signal data.

        Parameters
        ----------
        speaker_id : str
            Speaker ID
        start : float
            Start time
        end : float
            End time

        Returns
        -------
        dict
            Formatted signal data
        """
        return {
            "speaker": speaker_id,
            "start": start,
            "end": end,
            "duration": end - start,
        }

    def format_error_data(
        self,
        error_message: str,
        error_type: str,
    ) -> Dict[str, Any]:
        """
        Format error signal data.

        Parameters
        ----------
        error_message : str
            Error message
        error_type : str
            Error type

        Returns
        -------
        dict
            Formatted signal data
        """
        return {
            "message": error_message,
            "type": error_type,
        }

    def post_application_message(
        self,
        message_name: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Post application message to bus.

        Parameters
        ----------
        message_name : str
            Message name
        data : dict
            Message data
        """
        if Gst is None or self.element is None:
            return

        # Create structure
        structure = self._dict_to_structure(message_name, data)

        # Create application message
        message = Gst.Message.new_application(self.element, structure)

        # Post to bus
        bus = self.element.get_bus()
        if bus:
            bus.post(message)

    def post_element_message(
        self,
        message_name: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Post element message to bus.

        Parameters
        ----------
        message_name : str
            Message name
        data : dict
            Message data
        """
        if Gst is None or self.element is None:
            return

        # Create structure
        structure = self._dict_to_structure(message_name, data)

        # Create element message
        message = Gst.Message.new_element(self.element, structure)

        # Post to bus
        bus = self.element.get_bus()
        if bus:
            bus.post(message)

    def create_custom_event(
        self,
        event_name: str,
        data: Dict[str, Any],
    ) -> Optional[Any]:
        """
        Create a custom GStreamer event.

        Parameters
        ----------
        event_name : str
            Event name
        data : dict
            Event data

        Returns
        -------
        Gst.Event or None
            Custom event
        """
        if Gst is None:
            return None

        # Create structure
        structure = self._dict_to_structure(event_name, data)

        # Create custom downstream event
        event = Gst.Event.new_custom(
            Gst.EventType.CUSTOM_DOWNSTREAM,
            structure
        )

        return event

    def send_event_downstream(
        self,
        event_name: str,
        data: Dict[str, Any],
    ) -> bool:
        """
        Send custom event downstream.

        Parameters
        ----------
        event_name : str
            Event name
        data : dict
            Event data

        Returns
        -------
        bool
            True if event was sent successfully
        """
        if Gst is None or self.element is None:
            return False

        # Create event
        event = self.create_custom_event(event_name, data)
        if event is None:
            return False

        # Get source pad and send event
        src_pad = self.element.get_static_pad("src")
        if src_pad:
            return src_pad.push_event(event)

        return False

    def _post_error_message(
        self,
        error_message: str,
        error_type: str,
    ) -> None:
        """
        Post GStreamer error message to bus.

        Parameters
        ----------
        error_message : str
            Error description
        error_type : str
            Error type
        """
        if Gst is None or self.element is None:
            return

        if GLib is None:
            return

        # Create GError
        gerror = GLib.Error.new_literal(
            GLib.quark_from_string("pyannote"),
            1,
            f"{error_type}: {error_message}"
        )

        # Create error message
        message = Gst.Message.new_error(
            self.element,
            gerror,
            error_message
        )

        # Post to bus
        bus = self.element.get_bus()
        if bus:
            bus.post(message)

    def _dict_to_structure(
        self,
        name: str,
        data: Dict[str, Any],
    ) -> Any:
        """
        Convert dict to GStreamer structure.

        Parameters
        ----------
        name : str
            Structure name
        data : dict
            Data to convert

        Returns
        -------
        Gst.Structure
            GStreamer structure
        """
        if Gst is None:
            return None

        # Create structure
        structure = Gst.Structure.new_empty(name)

        # Add fields
        for key, value in data.items():
            # Convert value to appropriate GValue type
            if isinstance(value, bool):
                structure.set_value(key, value)
            elif isinstance(value, int):
                structure.set_value(key, value)
            elif isinstance(value, float):
                structure.set_value(key, value)
            elif isinstance(value, str):
                structure.set_value(key, value)
            else:
                # Convert to string for complex types
                structure.set_value(key, str(value))

        return structure
