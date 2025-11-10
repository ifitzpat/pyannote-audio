"""
Phase 5 Tests: Control Interface

Tests for control message handling:
- Parsing control messages
- Executing commands
- Parameter updates
- Model management
- State queries
"""

import pytest
import json
from unittest.mock import MagicMock, patch, call


@pytest.mark.unit
class TestControlMessageParser:
    """Test parsing control messages."""

    def test_parser_can_be_created(self):
        """Test that ControlMessageParser can be instantiated."""
        from gst_pyannote.control_interface import ControlMessageParser

        parser = ControlMessageParser()
        assert parser is not None

    def test_parse_json_message(self):
        """Test parsing JSON control message."""
        from gst_pyannote.control_interface import ControlMessageParser

        parser = ControlMessageParser()

        json_str = '{"command": "load_model", "model_name": "pyannote/speaker-diarization-3.1"}'
        message = parser.parse(json_str)

        assert message is not None
        assert message["command"] == "load_model"
        assert message["model_name"] == "pyannote/speaker-diarization-3.1"

    def test_parse_handles_invalid_json(self):
        """Test parser handles invalid JSON gracefully."""
        from gst_pyannote.control_interface import ControlMessageParser

        parser = ControlMessageParser()

        invalid_json = '{invalid json'
        message = parser.parse(invalid_json)

        # Should return None or raise exception
        assert message is None or "error" in message

    def test_parse_validates_command_field(self):
        """Test parser requires 'command' field."""
        from gst_pyannote.control_interface import ControlMessageParser

        parser = ControlMessageParser()

        # Missing command field
        json_str = '{"model_name": "pyannote/speaker-diarization-3.1"}'
        result = parser.parse(json_str)

        assert result is None or "error" in result

    def test_parse_extracts_all_fields(self):
        """Test parser extracts all message fields."""
        from gst_pyannote.control_interface import ControlMessageParser

        parser = ControlMessageParser()

        json_str = '{"command": "set_parameter", "parameters": {"min_speakers": 2}, "request_id": "123"}'
        message = parser.parse(json_str)

        assert message["command"] == "set_parameter"
        assert message["parameters"]["min_speakers"] == 2
        assert message["request_id"] == "123"


@pytest.mark.unit
class TestControlHandler:
    """Test control command handler."""

    def test_handler_can_be_created(self):
        """Test that ControlHandler can be instantiated."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()
        assert handler is not None

    def test_handler_stores_references(self):
        """Test handler stores element and manager references."""
        from gst_pyannote.control_interface import ControlHandler

        mock_element = MagicMock()
        mock_manager = MagicMock()
        mock_worker = MagicMock()

        handler = ControlHandler(
            element=mock_element,
            pipeline_manager=mock_manager,
            inference_worker=mock_worker
        )

        assert handler.element is mock_element
        assert handler.pipeline_manager is mock_manager
        assert handler.inference_worker is mock_worker

    def test_handler_has_command_registry(self):
        """Test handler has command registry."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()
        assert hasattr(handler, "commands")
        assert isinstance(handler.commands, dict)


@pytest.mark.unit
class TestLoadModelCommand:
    """Test load_model command."""

    def test_load_model_command_calls_pipeline_manager(self):
        """Test load_model calls pipeline manager."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "load_model",
            "model_name": "pyannote/speaker-diarization-3.1"
        }

        response = handler.handle_message(message)

        # Should call load_pipeline
        mock_manager.load_pipeline.assert_called_once_with(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=None
        )

    def test_load_model_with_auth_token(self):
        """Test load_model with authentication token."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "load_model",
            "model_name": "pyannote/speaker-diarization-3.1",
            "auth_token": "hf_xxxxxxxxxxxx"
        }

        handler.handle_message(message)

        mock_manager.load_pipeline.assert_called_once_with(
            "pyannote/speaker-diarization-3.1",
            use_auth_token="hf_xxxxxxxxxxxx"
        )

    def test_load_model_returns_success_response(self):
        """Test load_model returns success response."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "load_model",
            "model_name": "pyannote/speaker-diarization-3.1"
        }

        response = handler.handle_message(message)

        assert response is not None
        assert response["status"] == "success"
        assert response["command"] == "load_model"

    def test_load_model_handles_errors(self):
        """Test load_model handles errors gracefully."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        mock_manager.load_pipeline.side_effect = Exception("Model not found")

        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "load_model",
            "model_name": "invalid/model"
        }

        response = handler.handle_message(message)

        assert response["status"] == "error"
        assert "Model not found" in response["message"]


@pytest.mark.unit
class TestUnloadModelCommand:
    """Test unload_model command."""

    def test_unload_model_calls_pipeline_manager(self):
        """Test unload_model calls pipeline manager."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {"command": "unload_model"}

        handler.handle_message(message)

        mock_manager.unload_pipeline.assert_called_once()

    def test_unload_model_returns_success(self):
        """Test unload_model returns success response."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {"command": "unload_model"}
        response = handler.handle_message(message)

        assert response["status"] == "success"
        assert response["command"] == "unload_model"


@pytest.mark.unit
class TestSetParameterCommand:
    """Test set_parameter command."""

    def test_set_parameter_updates_pipeline_manager(self):
        """Test set_parameter updates pipeline manager parameters."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "set_parameter",
            "parameters": {
                "min_speakers": 2,
                "max_speakers": 10
            }
        }

        handler.handle_message(message)

        mock_manager.update_parameters.assert_called_once_with({
            "min_speakers": 2,
            "max_speakers": 10
        })

    def test_set_parameter_updates_element_properties(self):
        """Test set_parameter can update element properties."""
        from gst_pyannote.control_interface import ControlHandler

        mock_element = MagicMock()
        mock_manager = MagicMock()
        handler = ControlHandler(element=mock_element, pipeline_manager=mock_manager)

        message = {
            "command": "set_parameter",
            "parameters": {
                "window_duration": 20.0,
                "inference_enabled": False
            }
        }

        handler.handle_message(message)

        # Should set element properties
        assert mock_element.set_property.called

    def test_set_parameter_returns_updated_values(self):
        """Test set_parameter returns updated parameter values."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        mock_manager.get_parameters.return_value = {
            "min_speakers": 2,
            "max_speakers": 10
        }

        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "set_parameter",
            "parameters": {"min_speakers": 2}
        }

        response = handler.handle_message(message)

        assert response["status"] == "success"
        assert "parameters" in response


@pytest.mark.unit
class TestGetStateCommand:
    """Test get_state command."""

    def test_get_state_returns_pipeline_status(self):
        """Test get_state returns pipeline loaded status."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        mock_manager.is_loaded.return_value = True
        mock_manager.model_name = "pyannote/speaker-diarization-3.1"

        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {"command": "get_state"}
        response = handler.handle_message(message)

        assert response["status"] == "success"
        assert response["state"]["pipeline_loaded"] is True
        assert response["state"]["model_name"] == "pyannote/speaker-diarization-3.1"

    def test_get_state_returns_worker_status(self):
        """Test get_state returns worker status."""
        from gst_pyannote.control_interface import ControlHandler

        mock_worker = MagicMock()
        mock_worker.running = True
        mock_worker.get_queue_size.return_value = 3

        handler = ControlHandler(inference_worker=mock_worker)

        message = {"command": "get_state"}
        response = handler.handle_message(message)

        assert response["state"]["worker_running"] is True
        assert response["state"]["queue_size"] == 3

    def test_get_state_returns_parameters(self):
        """Test get_state returns current parameters."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        mock_manager.get_parameters.return_value = {
            "min_speakers": 2,
            "max_speakers": 10
        }

        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {"command": "get_state"}
        response = handler.handle_message(message)

        assert "parameters" in response["state"]
        assert response["state"]["parameters"]["min_speakers"] == 2


@pytest.mark.unit
class TestPauseResumeCommands:
    """Test pause_inference and resume_inference commands."""

    def test_pause_inference_stops_worker(self):
        """Test pause_inference stops the worker."""
        from gst_pyannote.control_interface import ControlHandler

        mock_worker = MagicMock()
        handler = ControlHandler(inference_worker=mock_worker)

        message = {"command": "pause_inference"}
        response = handler.handle_message(message)

        mock_worker.stop.assert_called_once()
        assert response["status"] == "success"

    def test_resume_inference_starts_worker(self):
        """Test resume_inference starts the worker."""
        from gst_pyannote.control_interface import ControlHandler

        mock_worker = MagicMock()
        handler = ControlHandler(inference_worker=mock_worker)

        message = {"command": "resume_inference"}
        response = handler.handle_message(message)

        mock_worker.start.assert_called_once()
        assert response["status"] == "success"


@pytest.mark.unit
class TestResetCommand:
    """Test reset command."""

    def test_reset_clears_worker_queue(self):
        """Test reset clears the inference worker queue."""
        from gst_pyannote.control_interface import ControlHandler

        mock_worker = MagicMock()
        handler = ControlHandler(inference_worker=mock_worker)

        message = {"command": "reset"}
        handler.handle_message(message)

        mock_worker.clear_queue.assert_called_once()

    def test_reset_returns_success(self):
        """Test reset returns success response."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()

        message = {"command": "reset"}
        response = handler.handle_message(message)

        assert response["status"] == "success"


@pytest.mark.unit
class TestUnknownCommand:
    """Test handling of unknown commands."""

    def test_unknown_command_returns_error(self):
        """Test unknown command returns error response."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()

        message = {"command": "unknown_command"}
        response = handler.handle_message(message)

        assert response["status"] == "error"
        assert "unknown" in response["message"].lower()


@pytest.mark.unit
class TestResponseFormatting:
    """Test response message formatting."""

    def test_response_includes_request_id(self):
        """Test response includes request_id if provided."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager)

        message = {
            "command": "get_state",
            "request_id": "abc-123"
        }

        response = handler.handle_message(message)

        assert response["request_id"] == "abc-123"

    def test_response_has_timestamp(self):
        """Test response includes timestamp."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()

        message = {"command": "get_state"}
        response = handler.handle_message(message)

        assert "timestamp" in response
        assert isinstance(response["timestamp"], float)

    def test_response_includes_command_echo(self):
        """Test response echoes the command."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()

        message = {"command": "get_state"}
        response = handler.handle_message(message)

        assert response["command"] == "get_state"


@pytest.mark.unit
class TestControlEventHandler:
    """Test GStreamer event handling for control pad."""

    @patch('gst_pyannote.control_interface.Gst')
    def test_extract_message_from_event(self, mock_gst):
        """Test extracting control message from GStreamer event."""
        from gst_pyannote.control_interface import ControlEventHandler

        mock_event = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_string.return_value = '{"command": "get_state"}'
        mock_event.get_structure.return_value = mock_structure

        handler = ControlEventHandler()
        message = handler.extract_message(mock_event)

        assert message is not None
        assert message["command"] == "get_state"

    @patch('gst_pyannote.control_interface.Gst')
    def test_create_response_event(self, mock_gst):
        """Test creating GStreamer event with response."""
        from gst_pyannote.control_interface import ControlEventHandler

        mock_gst.Structure.new_from_string = MagicMock()
        mock_gst.Event.new_custom = MagicMock()

        handler = ControlEventHandler()

        response = {
            "status": "success",
            "command": "get_state",
            "state": {}
        }

        event = handler.create_response_event(response)

        # Should create custom event
        assert mock_gst.Event.new_custom.called


@pytest.mark.unit
class TestCommandValidation:
    """Test command parameter validation."""

    def test_load_model_requires_model_name(self):
        """Test load_model requires model_name parameter."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()

        # Missing model_name
        message = {"command": "load_model"}
        response = handler.handle_message(message)

        assert response["status"] == "error"
        assert "model_name" in response["message"].lower()

    def test_set_parameter_requires_parameters(self):
        """Test set_parameter requires parameters field."""
        from gst_pyannote.control_interface import ControlHandler

        handler = ControlHandler()

        # Missing parameters
        message = {"command": "set_parameter"}
        response = handler.handle_message(message)

        assert response["status"] == "error"


@pytest.mark.unit
class TestAsyncCommandExecution:
    """Test asynchronous command execution."""

    def test_handler_can_execute_async(self):
        """Test handler can execute commands asynchronously."""
        from gst_pyannote.control_interface import ControlHandler

        mock_manager = MagicMock()
        handler = ControlHandler(pipeline_manager=mock_manager, async_mode=True)

        message = {"command": "load_model", "model_name": "test"}

        # Should return immediately with "processing" status
        response = handler.handle_message(message)

        # In async mode, should get immediate response
        assert response is not None

    def test_async_completion_callback(self):
        """Test async command completion callback."""
        from gst_pyannote.control_interface import ControlHandler

        mock_callback = MagicMock()
        handler = ControlHandler(on_command_complete=mock_callback)

        message = {"command": "get_state", "request_id": "123"}
        handler.handle_message(message)

        # Callback should be called with response
        assert mock_callback.called
