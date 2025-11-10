"""
Phase 1 Tests: Basic Element Structure (Mock-based)

These tests use mocks to verify element structure without requiring
a fully functional GStreamer environment. They test the Python code structure
and logic without actually running GStreamer.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


@pytest.mark.unit
class TestElementStructure:
    """Test element class structure and methods."""

    @patch('gst_pyannote.element.gi')
    @patch('gst_pyannote.pads.gi')
    def test_element_class_exists(self, mock_pads_gi, mock_element_gi):
        """Test that GstPyannote class is defined."""
        # Mock GStreamer components
        mock_element_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})
        mock_element_gi.repository.GObject = MagicMock()
        mock_element_gi.repository.Gst = MagicMock()
        mock_pads_gi.repository.Gst = MagicMock()

        # Now import (will use mocked gi)
        from gst_pyannote.element import GstPyannote

        assert GstPyannote is not None
        assert hasattr(GstPyannote, '__gstmetadata__')

    @patch('gst_pyannote.element.gi')
    @patch('gst_pyannote.pads.gi')
    def test_element_metadata_structure(self, mock_pads_gi, mock_element_gi):
        """Test element has proper metadata tuple."""
        # Setup mocks
        mock_element_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})
        mock_element_gi.repository.GObject = MagicMock()
        mock_element_gi.repository.Gst = MagicMock()
        mock_pads_gi.repository.Gst = MagicMock()

        from gst_pyannote.element import GstPyannote

        metadata = GstPyannote.__gstmetadata__
        assert len(metadata) == 4
        assert isinstance(metadata[0], str)  # Long name
        assert isinstance(metadata[1], str)  # Classification
        assert isinstance(metadata[2], str)  # Description
        assert isinstance(metadata[3], str)  # Author

        # Check content
        assert "diarization" in metadata[0].lower() or "pyannote" in metadata[0].lower()
        assert "filter" in metadata[1].lower() or "audio" in metadata[1].lower()

    @patch('gst_pyannote.element.gi')
    @patch('gst_pyannote.pads.gi')
    def test_element_has_pad_templates(self, mock_pads_gi, mock_element_gi):
        """Test element defines pad templates."""
        # Setup mocks
        mock_element_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})
        mock_element_gi.repository.GObject = MagicMock()
        mock_element_gi.repository.Gst = MagicMock()
        mock_pads_gi.repository.Gst = MagicMock()

        from gst_pyannote.element import GstPyannote

        assert hasattr(GstPyannote, '__gsttemplates__')
        templates = GstPyannote.__gsttemplates__
        assert len(templates) == 4  # audio_sink, audio_src, json_src, control_sink

    @patch('gst_pyannote.element.gi')
    @patch('gst_pyannote.pads.gi')
    def test_element_has_properties(self, mock_pads_gi, mock_element_gi):
        """Test element defines GObject properties."""
        # Setup mocks
        mock_element_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})
        mock_element_gi.repository.GObject = MagicMock()
        mock_element_gi.repository.Gst = MagicMock()
        mock_pads_gi.repository.Gst = MagicMock()

        from gst_pyannote.element import GstPyannote

        assert hasattr(GstPyannote, '__gproperties__')
        props = GstPyannote.__gproperties__

        # Check required properties exist
        assert "model-name" in props
        assert "min-speakers" in props
        assert "max-speakers" in props
        assert "window-duration" in props
        assert "inference-enabled" in props
        assert "device" in props

    @patch('gst_pyannote.element.gi')
    @patch('gst_pyannote.pads.gi')
    def test_property_specifications(self, mock_pads_gi, mock_element_gi):
        """Test property specifications are correct."""
        # Setup mocks
        mock_element_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})
        mock_element_gi.repository.GObject = MagicMock()
        mock_element_gi.repository.Gst = MagicMock()
        mock_pads_gi.repository.Gst = MagicMock()

        from gst_pyannote.element import GstPyannote

        props = GstPyannote.__gproperties__

        # model-name should be string
        assert props["model-name"][0] == str

        # min-speakers should be int with range
        assert props["min-speakers"][0] == int
        assert props["min-speakers"][3] >= 0  # Min value
        assert props["min-speakers"][4] > 0   # Max value

        # window-duration should be float
        assert props["window-duration"][0] == float
        assert props["window-duration"][3] > 0  # Min value

        # inference-enabled should be bool
        assert props["inference-enabled"][0] == bool


@pytest.mark.unit
class TestElementInitialization:
    """Test element initialization logic."""

    @patch('gst_pyannote.element.Gst')
    @patch('gst_pyannote.element.GstBase')
    @patch('gst_pyannote.element.GObject')
    @patch('gst_pyannote.pads.Gst')
    def test_element_init_sets_defaults(self, mock_pads_gst, mock_gobject, mock_gstbase, mock_gst):
        """Test element __init__ sets default values."""
        # Setup mocks
        mock_gstbase.BaseTransform = type('BaseTransform', (), {
            '__init__': lambda self: None,
            'add_pad': MagicMock(),
            'set_passthrough': MagicMock(),
            'set_in_place': MagicMock(),
        })
        mock_gst.Pad.new_from_template = MagicMock()
        mock_gst.Pad.new_from_template.return_value = MagicMock()
        mock_pads_gst.PadTemplate.new = MagicMock()
        mock_pads_gst.PadDirection.SRC = 1
        mock_pads_gst.PadDirection.SINK = 2
        mock_pads_gst.PadPresence.ALWAYS = 1
        mock_pads_gst.Caps.from_string = MagicMock()

        from gst_pyannote.element import GstPyannote

        element = GstPyannote()

        # Check defaults
        assert element.model_name == "pyannote/speaker-diarization-3.1"
        assert element.min_speakers == 0
        assert element.max_speakers == 0
        assert element.window_duration == 30.0
        assert element.overlap_duration == 5.0
        assert element.inference_enabled == True
        assert element.device == "cuda"

    @patch('gst_pyannote.element.Gst')
    @patch('gst_pyannote.element.GstBase')
    @patch('gst_pyannote.element.GObject')
    @patch('gst_pyannote.pads.Gst')
    def test_element_creates_extra_pads(self, mock_pads_gst, mock_gobject, mock_gstbase, mock_gst):
        """Test element creates JSON and control pads."""
        # Setup mocks
        mock_gstbase.BaseTransform = type('BaseTransform', (), {
            '__init__': lambda self: None,
            'add_pad': MagicMock(),
            'set_passthrough': MagicMock(),
            'set_in_place': MagicMock(),
        })
        mock_pad = MagicMock()
        mock_gst.Pad.new_from_template = MagicMock(return_value=mock_pad)
        mock_pads_gst.PadTemplate.new = MagicMock()
        mock_pads_gst.PadDirection.SRC = 1
        mock_pads_gst.PadDirection.SINK = 2
        mock_pads_gst.PadPresence.ALWAYS = 1
        mock_pads_gst.Caps.from_string = MagicMock()

        from gst_pyannote.element import GstPyannote

        element = GstPyannote()

        # Check pads were created
        assert element.json_srcpad is not None
        assert element.control_sinkpad is not None

        # Check add_pad was called
        assert element.add_pad.call_count == 2


@pytest.mark.unit
class TestElementMethods:
    """Test element method implementations."""

    @patch('gst_pyannote.element.Gst')
    @patch('gst_pyannote.element.GstBase')
    @patch('gst_pyannote.element.GObject')
    @patch('gst_pyannote.pads.Gst')
    def test_get_property_method(self, mock_pads_gst, mock_gobject, mock_gstbase, mock_gst):
        """Test do_get_property returns correct values."""
        # Setup mocks
        mock_gstbase.BaseTransform = type('BaseTransform', (), {
            '__init__': lambda self: None,
            'add_pad': MagicMock(),
            'set_passthrough': MagicMock(),
            'set_in_place': MagicMock(),
        })
        mock_gst.Pad.new_from_template = MagicMock()
        mock_gst.Pad.new_from_template.return_value = MagicMock()
        mock_pads_gst.PadTemplate.new = MagicMock()
        mock_pads_gst.PadDirection.SRC = 1
        mock_pads_gst.PadDirection.SINK = 2
        mock_pads_gst.PadPresence.ALWAYS = 1
        mock_pads_gst.Caps.from_string = MagicMock()

        from gst_pyannote.element import GstPyannote

        element = GstPyannote()

        # Create mock property spec
        mock_prop = MagicMock()
        mock_prop.name = "model-name"

        result = element.do_get_property(mock_prop)
        assert result == "pyannote/speaker-diarization-3.1"

    @patch('gst_pyannote.element.Gst')
    @patch('gst_pyannote.element.GstBase')
    @patch('gst_pyannote.element.GObject')
    @patch('gst_pyannote.pads.Gst')
    def test_set_property_method(self, mock_pads_gst, mock_gobject, mock_gstbase, mock_gst):
        """Test do_set_property updates values."""
        # Setup mocks
        mock_gstbase.BaseTransform = type('BaseTransform', (), {
            '__init__': lambda self: None,
            'add_pad': MagicMock(),
            'set_passthrough': MagicMock(),
            'set_in_place': MagicMock(),
        })
        mock_gst.Pad.new_from_template = MagicMock()
        mock_gst.Pad.new_from_template.return_value = MagicMock()
        mock_pads_gst.PadTemplate.new = MagicMock()
        mock_pads_gst.PadDirection.SRC = 1
        mock_pads_gst.PadDirection.SINK = 2
        mock_pads_gst.PadPresence.ALWAYS = 1
        mock_pads_gst.Caps.from_string = MagicMock()

        from gst_pyannote.element import GstPyannote

        element = GstPyannote()

        # Create mock property spec
        mock_prop = MagicMock()
        mock_prop.name = "min-speakers"

        element.do_set_property(mock_prop, 5)
        assert element.min_speakers == 5

    @patch('gst_pyannote.element.Gst')
    @patch('gst_pyannote.element.GstBase')
    @patch('gst_pyannote.element.GObject')
    @patch('gst_pyannote.pads.Gst')
    def test_inference_enabled_toggles_passthrough(self, mock_pads_gst, mock_gobject, mock_gstbase, mock_gst):
        """Test that changing inference-enabled toggles passthrough mode."""
        # Setup mocks
        mock_gstbase.BaseTransform = type('BaseTransform', (), {
            '__init__': lambda self: None,
            'add_pad': MagicMock(),
            'set_passthrough': MagicMock(),
            'set_in_place': MagicMock(),
        })
        mock_gst.Pad.new_from_template = MagicMock()
        mock_gst.Pad.new_from_template.return_value = MagicMock()
        mock_pads_gst.PadTemplate.new = MagicMock()
        mock_pads_gst.PadDirection.SRC = 1
        mock_pads_gst.PadDirection.SINK = 2
        mock_pads_gst.PadPresence.ALWAYS = 1
        mock_pads_gst.Caps.from_string = MagicMock()

        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        element.set_passthrough.reset_mock()

        # Disable inference
        mock_prop = MagicMock()
        mock_prop.name = "inference-enabled"
        element.do_set_property(mock_prop, False)

        # Should set passthrough to True
        element.set_passthrough.assert_called_with(True)

        # Enable inference
        element.do_set_property(mock_prop, True)

        # Should set passthrough to False
        element.set_passthrough.assert_called_with(False)


@pytest.mark.unit
class TestPadTemplates:
    """Test pad template definitions."""

    @patch('gst_pyannote.pads.Gst')
    def test_audio_sink_caps(self, mock_gst):
        """Test audio sink pad capabilities."""
        mock_gst.Caps.from_string = MagicMock()
        mock_gst.PadTemplate.new = MagicMock()
        mock_gst.PadDirection.SINK = 2
        mock_gst.PadPresence.ALWAYS = 1

        from gst_pyannote.pads import AUDIO_SINK_CAPS, AUDIO_SINK_TEMPLATE

        # Check caps string was created
        assert mock_gst.Caps.from_string.called

        # Check it includes F32LE format
        caps_string = mock_gst.Caps.from_string.call_args[0][0]
        assert "F32LE" in caps_string
        assert "audio/x-raw" in caps_string

    @patch('gst_pyannote.pads.Gst')
    def test_json_src_caps(self, mock_gst):
        """Test JSON source pad capabilities."""
        mock_gst.Caps.from_string = MagicMock()
        mock_gst.PadTemplate.new = MagicMock()
        mock_gst.PadDirection.SRC = 1
        mock_gst.PadPresence.ALWAYS = 1

        from gst_pyannote.pads import JSON_SRC_CAPS, JSON_SRC_TEMPLATE

        # Check application/json caps
        calls = [call[0][0] for call in mock_gst.Caps.from_string.call_args_list]
        assert any("application/json" in call for call in calls)
