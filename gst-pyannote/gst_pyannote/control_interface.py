"""
Control Interface

Handles control messages for runtime configuration of the GstPyannote element.
Supports commands for model loading, parameter updates, and state queries.
"""

import json
import time
from typing import Optional, Dict, Any, Callable

# Try to import GStreamer, but allow tests to mock it
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
except (ImportError, ValueError):
    Gst = None


class ControlMessageParser:
    """
    Parses control messages from JSON strings.

    Control messages have the format:
    {
        "command": "load_model",
        "model_name": "pyannote/speaker-diarization-3.1",
        "request_id": "optional-id"
    }
    """

    def parse(self, json_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse a JSON control message.

        Parameters
        ----------
        json_str : str
            JSON-formatted control message

        Returns
        -------
        dict or None
            Parsed message dict, or None if invalid
        """
        try:
            message = json.loads(json_str)

            # Validate required command field
            if not isinstance(message, dict):
                return {"error": "Message must be a JSON object"}

            if "command" not in message:
                return {"error": "Missing required 'command' field"}

            return message

        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {str(e)}"}
        except Exception as e:
            return {"error": f"Parse error: {str(e)}"}


class ControlHandler:
    """
    Handles control commands for the GstPyannote element.

    Dispatches commands to appropriate handlers and manages
    interactions with the pipeline manager and inference worker.

    Parameters
    ----------
    element : Gst.Element, optional
        GStreamer element (for property updates)
    pipeline_manager : PyannotePipelineManager, optional
        Pipeline manager for model operations
    inference_worker : InferenceWorker, optional
        Inference worker for queue management
    async_mode : bool, optional
        If True, commands execute asynchronously. Default: False
    on_command_complete : callable, optional
        Callback when async command completes: on_command_complete(response)
    """

    def __init__(
        self,
        element: Optional[Any] = None,
        pipeline_manager: Optional[Any] = None,
        inference_worker: Optional[Any] = None,
        async_mode: bool = False,
        on_command_complete: Optional[Callable[[Dict], None]] = None,
    ):
        self.element = element
        self.pipeline_manager = pipeline_manager
        self.inference_worker = inference_worker
        self.async_mode = async_mode
        self.on_command_complete = on_command_complete

        # Command registry
        self.commands = {
            "load_model": self._handle_load_model,
            "unload_model": self._handle_unload_model,
            "set_parameter": self._handle_set_parameter,
            "get_state": self._handle_get_state,
            "pause_inference": self._handle_pause_inference,
            "resume_inference": self._handle_resume_inference,
            "reset": self._handle_reset,
        }

    def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a control message and execute the command.

        Parameters
        ----------
        message : dict
            Parsed control message with 'command' field

        Returns
        -------
        dict
            Response message with status, command, and result data
        """
        command = message.get("command")
        request_id = message.get("request_id")

        # Build response template
        response = {
            "status": "success",
            "command": command,
            "timestamp": time.time(),
        }

        if request_id:
            response["request_id"] = request_id

        # Dispatch to handler
        if command not in self.commands:
            response["status"] = "error"
            response["message"] = f"Unknown command: {command}"
            return response

        try:
            handler = self.commands[command]
            result = handler(message)

            if result:
                response.update(result)

            # Call completion callback if registered
            if self.on_command_complete:
                self.on_command_complete(response)

            return response

        except Exception as e:
            response["status"] = "error"
            response["message"] = str(e)
            return response

    def _handle_load_model(self, message: Dict) -> Dict:
        """Handle load_model command."""
        model_name = message.get("model_name")

        if not model_name:
            raise ValueError("Missing required parameter: model_name")

        if self.pipeline_manager is None:
            raise RuntimeError("Pipeline manager not available")

        auth_token = message.get("auth_token")

        self.pipeline_manager.load_pipeline(
            model_name,
            use_auth_token=auth_token,
        )

        return {}

    def _handle_unload_model(self, message: Dict) -> Dict:
        """Handle unload_model command."""
        if self.pipeline_manager is None:
            raise RuntimeError("Pipeline manager not available")

        self.pipeline_manager.unload_pipeline()

        return {}

    def _handle_set_parameter(self, message: Dict) -> Dict:
        """Handle set_parameter command."""
        parameters = message.get("parameters")

        if not parameters:
            raise ValueError("Missing required field: parameters")

        # Update pipeline manager parameters
        if self.pipeline_manager:
            self.pipeline_manager.update_parameters(parameters)

        # Update element properties if applicable
        if self.element:
            for key, value in parameters.items():
                # Try to set as element property
                try:
                    self.element.set_property(key, value)
                except:
                    pass  # Not all parameters are element properties

        # Return current parameters
        result = {}
        if self.pipeline_manager:
            result["parameters"] = self.pipeline_manager.get_parameters()

        return result

    def _handle_get_state(self, message: Dict) -> Dict:
        """Handle get_state command."""
        state = {}

        # Pipeline state
        if self.pipeline_manager:
            state["pipeline_loaded"] = self.pipeline_manager.is_loaded()
            if hasattr(self.pipeline_manager, "model_name"):
                state["model_name"] = self.pipeline_manager.model_name
            state["parameters"] = self.pipeline_manager.get_parameters()

        # Worker state
        if self.inference_worker:
            state["worker_running"] = self.inference_worker.running
            state["queue_size"] = self.inference_worker.get_queue_size()

        return {"state": state}

    def _handle_pause_inference(self, message: Dict) -> Dict:
        """Handle pause_inference command."""
        if self.inference_worker is None:
            raise RuntimeError("Inference worker not available")

        self.inference_worker.stop()

        return {}

    def _handle_resume_inference(self, message: Dict) -> Dict:
        """Handle resume_inference command."""
        if self.inference_worker is None:
            raise RuntimeError("Inference worker not available")

        self.inference_worker.start()

        return {}

    def _handle_reset(self, message: Dict) -> Dict:
        """Handle reset command."""
        if self.inference_worker:
            self.inference_worker.clear_queue()

        return {}


class ControlEventHandler:
    """
    Handles GStreamer events for control messages.

    Converts between GStreamer custom events and control messages.
    """

    def extract_message(self, event: Any) -> Optional[Dict]:
        """
        Extract control message from GStreamer event.

        Parameters
        ----------
        event : Gst.Event
            GStreamer custom event containing control message

        Returns
        -------
        dict or None
            Parsed control message
        """
        if Gst is None:
            return None

        # Get structure from event
        structure = event.get_structure()
        if structure is None:
            return None

        # Extract JSON string
        json_str = structure.get_string("message")
        if not json_str:
            return None

        # Parse message
        parser = ControlMessageParser()
        return parser.parse(json_str)

    def create_response_event(self, response: Dict) -> Optional[Any]:
        """
        Create GStreamer event containing response message.

        Parameters
        ----------
        response : dict
            Response message to wrap in event

        Returns
        -------
        Gst.Event or None
            GStreamer custom event
        """
        if Gst is None:
            return None

        # Serialize response to JSON
        json_str = json.dumps(response)

        # Create structure
        structure = Gst.Structure.new_from_string(
            f"pyannote-control-response, message=(string){json_str}"
        )

        # Create custom event
        event = Gst.Event.new_custom(
            Gst.EventType.CUSTOM_DOWNSTREAM,
            structure
        )

        return event
