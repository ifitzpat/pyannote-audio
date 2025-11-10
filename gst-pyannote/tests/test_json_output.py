"""
Phase 4 Tests: JSON Output Handler

Tests for the JSON output functionality that:
- Formats diarization results as JSON
- Creates GStreamer buffers
- Emits buffers on the json_src pad
"""

import pytest
import json
from unittest.mock import MagicMock, patch, call


@pytest.mark.unit
class TestJSONOutputHandler:
    """Test JSON output handler initialization."""

    def test_handler_can_be_created(self):
        """Test that JSONOutputHandler can be instantiated."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()
        assert handler is not None

    def test_handler_stores_element_reference(self):
        """Test handler stores GStreamer element reference."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        handler = JSONOutputHandler(mock_element)

        assert handler.element is mock_element


@pytest.mark.unit
class TestResultFormatting:
    """Test formatting diarization results to JSON."""

    def test_format_results_to_json(self):
        """Test converting results dict to JSON string."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [
                {"speaker": "SPEAKER_00", "start": 1.0, "end": 3.0},
                {"speaker": "SPEAKER_01", "start": 2.0, "end": 4.0},
            ],
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["events"] == results["events"]
        assert parsed["speakers"] == results["speakers"]

    def test_format_includes_metadata(self):
        """Test JSON includes metadata fields."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 10.0,
        }

        json_str = handler.format_json(results)
        parsed = json.loads(json_str)

        # Should include metadata
        assert "type" in parsed
        assert parsed["type"] == "diarization"
        assert "timestamp" in parsed
        assert parsed["timestamp"] == 10.0

    def test_format_handles_empty_events(self):
        """Test formatting with no events."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)
        parsed = json.loads(json_str)

        assert parsed["events"] == []
        assert parsed["speakers"] == []

    def test_format_rounds_timestamps(self):
        """Test that timestamps are rounded for cleaner JSON."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [
                {"speaker": "SPEAKER_00", "start": 1.23456, "end": 3.78901},
            ],
            "speakers": ["SPEAKER_00"],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)
        parsed = json.loads(json_str)

        # Should round to 3 decimal places
        assert parsed["events"][0]["start"] == 1.235
        assert parsed["events"][0]["end"] == 3.789

    def test_format_preserves_speaker_order(self):
        """Test that speaker order is preserved."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [],
            "speakers": ["SPEAKER_02", "SPEAKER_00", "SPEAKER_01"],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)
        parsed = json.loads(json_str)

        assert parsed["speakers"] == ["SPEAKER_02", "SPEAKER_00", "SPEAKER_01"]


@pytest.mark.unit
class TestGStreamerBufferCreation:
    """Test creating GStreamer buffers from JSON."""

    @patch('gst_pyannote.json_output.Gst')
    def test_create_buffer_from_json(self, mock_gst):
        """Test creating a GstBuffer containing JSON."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_buffer = MagicMock()
        mock_gst.Buffer.new_wrapped.return_value = mock_buffer

        handler = JSONOutputHandler()

        json_str = '{"test": "data"}'
        buffer = handler.create_buffer(json_str)

        # Should create buffer with JSON bytes
        mock_gst.Buffer.new_wrapped.assert_called_once()
        call_args = mock_gst.Buffer.new_wrapped.call_args[0][0]
        assert isinstance(call_args, bytes)
        assert b"test" in call_args

    @patch('gst_pyannote.json_output.Gst')
    def test_buffer_has_timestamp(self, mock_gst):
        """Test that buffer has proper PTS timestamp."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_buffer = MagicMock()
        mock_gst.Buffer.new_wrapped.return_value = mock_buffer

        handler = JSONOutputHandler()

        json_str = '{"timestamp": 10.5}'
        buffer = handler.create_buffer(json_str, timestamp=10.5)

        # Should set PTS (presentation timestamp)
        assert buffer.pts is not None

    @patch('gst_pyannote.json_output.Gst')
    def test_buffer_converts_seconds_to_nanoseconds(self, mock_gst):
        """Test timestamp conversion from seconds to nanoseconds."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_buffer = MagicMock()
        mock_gst.Buffer.new_wrapped.return_value = mock_buffer
        mock_gst.SECOND = 1000000000  # 1 second in nanoseconds

        handler = JSONOutputHandler()

        buffer = handler.create_buffer('{}', timestamp=5.0)

        # 5.0 seconds = 5000000000 nanoseconds
        assert buffer.pts == 5000000000

    @patch('gst_pyannote.json_output.Gst')
    def test_buffer_has_duration(self, mock_gst):
        """Test that buffer can have a duration."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_buffer = MagicMock()
        mock_gst.Buffer.new_wrapped.return_value = mock_buffer
        mock_gst.SECOND = 1000000000

        handler = JSONOutputHandler()

        buffer = handler.create_buffer('{}', timestamp=0.0, duration=1.0)

        # Duration in nanoseconds
        assert buffer.duration == 1000000000


@pytest.mark.unit
class TestBufferEmission:
    """Test emitting buffers on the json_src pad."""

    @patch('gst_pyannote.json_output.Gst')
    def test_emit_pushes_buffer_to_pad(self, mock_gst):
        """Test that emit() pushes buffer to the source pad."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        mock_pad = MagicMock()
        mock_element.get_static_pad.return_value = mock_pad

        mock_buffer = MagicMock()
        mock_gst.Buffer.new_wrapped.return_value = mock_buffer

        handler = JSONOutputHandler(mock_element)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        handler.emit_results(results)

        # Should get json_src pad
        mock_element.get_static_pad.assert_called_with("json_src")

        # Should push buffer
        mock_pad.push.assert_called_once()

    @patch('gst_pyannote.json_output.Gst')
    def test_emit_returns_flow_result(self, mock_gst):
        """Test that emit returns GstFlowReturn."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        mock_pad = MagicMock()
        mock_element.get_static_pad.return_value = mock_pad
        mock_pad.push.return_value = mock_gst.FlowReturn.OK

        handler = JSONOutputHandler(mock_element)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        flow_return = handler.emit_results(results)

        assert flow_return == mock_gst.FlowReturn.OK

    @patch('gst_pyannote.json_output.Gst')
    def test_emit_handles_no_pad(self, mock_gst):
        """Test emit handles case where pad doesn't exist."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        mock_element.get_static_pad.return_value = None

        handler = JSONOutputHandler(mock_element)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        # Should not crash
        flow_return = handler.emit_results(results)

        # Should return error
        assert flow_return == mock_gst.FlowReturn.ERROR

    @patch('gst_pyannote.json_output.Gst')
    def test_emit_handles_push_error(self, mock_gst):
        """Test emit handles push errors gracefully."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        mock_pad = MagicMock()
        mock_element.get_static_pad.return_value = mock_pad
        mock_pad.push.return_value = mock_gst.FlowReturn.ERROR

        handler = JSONOutputHandler(mock_element)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        flow_return = handler.emit_results(results)

        assert flow_return == mock_gst.FlowReturn.ERROR


@pytest.mark.unit
class TestCallbackIntegration:
    """Test integration as InferenceWorker callback."""

    @patch('gst_pyannote.json_output.Gst')
    def test_can_be_used_as_callback(self, mock_gst):
        """Test handler can be used as InferenceWorker callback."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        mock_pad = MagicMock()
        mock_element.get_static_pad.return_value = mock_pad

        handler = JSONOutputHandler(mock_element)

        # Should be callable
        assert callable(handler)

        # Should accept results dict
        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        handler(results)  # Call as callback

        # Should have pushed buffer
        mock_pad.push.assert_called_once()

    @patch('gst_pyannote.json_output.Gst')
    def test_multiple_results_emit_multiple_buffers(self, mock_gst):
        """Test that multiple calls emit multiple buffers."""
        from gst_pyannote.json_output import JSONOutputHandler

        mock_element = MagicMock()
        mock_pad = MagicMock()
        mock_element.get_static_pad.return_value = mock_pad

        handler = JSONOutputHandler(mock_element)

        # Emit multiple results
        for i in range(3):
            results = {
                "events": [],
                "speakers": [],
                "timestamp": float(i),
            }
            handler(results)

        # Should push 3 buffers
        assert mock_pad.push.call_count == 3


@pytest.mark.unit
class TestJSONSchema:
    """Test JSON output schema validation."""

    def test_output_has_required_fields(self):
        """Test that JSON output has all required fields."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [{"speaker": "SPEAKER_00", "start": 1.0, "end": 2.0}],
            "speakers": ["SPEAKER_00"],
            "timestamp": 5.0,
        }

        json_str = handler.format_json(results)
        parsed = json.loads(json_str)

        # Required fields
        required = ["type", "timestamp", "events", "speakers"]
        for field in required:
            assert field in parsed, f"Missing required field: {field}"

    def test_event_has_required_fields(self):
        """Test that each event has required fields."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        results = {
            "events": [{"speaker": "SPEAKER_00", "start": 1.0, "end": 2.0}],
            "speakers": ["SPEAKER_00"],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)
        parsed = json.loads(json_str)

        event = parsed["events"][0]
        assert "speaker" in event
        assert "start" in event
        assert "end" in event

    def test_output_is_valid_json(self):
        """Test that output is always valid JSON."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler()

        # Test with various inputs
        test_cases = [
            {"events": [], "speakers": [], "timestamp": 0.0},
            {"events": [{"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0}],
             "speakers": ["SPEAKER_00"], "timestamp": 0.0},
            {"events": [], "speakers": ["SPEAKER_00", "SPEAKER_01"],
             "timestamp": 100.5},
        ]

        for results in test_cases:
            json_str = handler.format_json(results)
            # Should not raise
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)


@pytest.mark.unit
class TestCompactJSON:
    """Test compact JSON formatting options."""

    def test_can_produce_compact_json(self):
        """Test option to produce compact JSON (no whitespace)."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler(compact=True)

        results = {
            "events": [{"speaker": "SPEAKER_00", "start": 1.0, "end": 2.0}],
            "speakers": ["SPEAKER_00"],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)

        # Compact should have no newlines
        assert '\n' not in json_str

    def test_can_produce_pretty_json(self):
        """Test option to produce pretty-printed JSON."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler(compact=False)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)

        # Pretty should have newlines and indentation
        assert '\n' in json_str
        assert '  ' in json_str  # 2-space indent


@pytest.mark.unit
class TestLineDelimitedJSON:
    """Test line-delimited JSON mode (JSONL)."""

    def test_jsonl_mode_adds_newline(self):
        """Test JSONL mode adds newline after each JSON object."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler(jsonl_mode=True)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)

        # Should end with newline
        assert json_str.endswith('\n')

    def test_jsonl_mode_is_compact(self):
        """Test JSONL mode produces compact single-line JSON."""
        from gst_pyannote.json_output import JSONOutputHandler

        handler = JSONOutputHandler(jsonl_mode=True)

        results = {
            "events": [],
            "speakers": [],
            "timestamp": 0.0,
        }

        json_str = handler.format_json(results)

        # Should be single line (only trailing newline)
        lines = json_str.split('\n')
        assert len(lines) == 2  # Content + empty from trailing \n
        assert lines[0]  # First line has content
        assert not lines[1]  # Second line is empty
