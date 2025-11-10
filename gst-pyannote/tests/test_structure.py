"""
Phase 1 Tests: Code Structure (No GStreamer Required)

These tests verify the code structure and logic without requiring
GStreamer to be functional. They test imports, class definitions,
and basic Python logic.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch


@pytest.mark.unit
class TestPackageStructure:
    """Test package structure and imports."""

    def test_package_imports(self):
        """Test that package can be imported."""
        import gst_pyannote

        assert gst_pyannote.__version__ == "0.1.0"

    def test_package_has_plugin_init(self):
        """Test that package exposes plugin_init."""
        import gst_pyannote

        assert hasattr(gst_pyannote, "plugin_init")
        assert callable(gst_pyannote.plugin_init)


@pytest.mark.unit
class TestElementClassDefinition:
    """Test element class structure without instantiation."""

    def test_element_module_can_be_mocked(self):
        """Test that we can mock gi and import element module."""
        # Mock gi before importing
        sys.modules['gi'] = MagicMock()
        sys.modules['gi.repository'] = MagicMock()

        try:
            # Now we can import (modules are cached, so need fresh import)
            import importlib
            import gst_pyannote.element as elem_module

            # Force reload to use mocked gi
            importlib.reload(elem_module)

            assert hasattr(elem_module, 'GstPyannote')
        finally:
            # Clean up mocks
            if 'gst_pyannote.element' in sys.modules:
                del sys.modules['gst_pyannote.element']
            if 'gst_pyannote.pads' in sys.modules:
                del sys.modules['gst_pyannote.pads']

    def test_element_metadata_defined(self):
        """Test element metadata is properly defined."""
        # Setup mock environment
        mock_gi = MagicMock()
        mock_gst = MagicMock()
        mock_gstbase = MagicMock()
        mock_gobject = MagicMock()

        # Create mock BaseTransform
        mock_gstbase.BaseTransform = type('BaseTransform', (), {})
        mock_gi.repository.Gst = mock_gst
        mock_gi.repository.GstBase = mock_gstbase
        mock_gi.repository.GObject = mock_gobject

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            # Check metadata
            assert hasattr(elem_module.GstPyannote, '__gstmetadata__')
            metadata = elem_module.GstPyannote.__gstmetadata__
            assert len(metadata) == 4
            assert isinstance(metadata[0], str)
            assert isinstance(metadata[1], str)
            assert isinstance(metadata[2], str)
            assert isinstance(metadata[3], str)

        finally:
            # Cleanup
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_element_properties_defined(self):
        """Test element GObject properties are defined."""
        # Setup mocks
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.GstBase = MagicMock()
        mock_gi.repository.GObject = MagicMock()
        mock_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            # Check properties
            assert hasattr(elem_module.GstPyannote, '__gproperties__')
            props = elem_module.GstPyannote.__gproperties__

            # Verify required properties
            required_props = [
                "model-name",
                "min-speakers",
                "max-speakers",
                "window-duration",
                "inference-enabled",
                "device",
            ]

            for prop_name in required_props:
                assert prop_name in props, f"Missing property: {prop_name}"

        finally:
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_element_pad_templates_defined(self):
        """Test element pad templates are defined."""
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.GstBase = MagicMock()
        mock_gi.repository.GObject = MagicMock()
        mock_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            # Check pad templates
            assert hasattr(elem_module.GstPyannote, '__gsttemplates__')
            templates = elem_module.GstPyannote.__gsttemplates__

            # Should have 4 pads: audio_sink, audio_src, json_src, control_sink
            assert len(templates) == 4

        finally:
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]


@pytest.mark.unit
class TestPropertySpecifications:
    """Test property specifications are correct."""

    def test_model_name_property_type(self):
        """Test model-name property is a string."""
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.GstBase = MagicMock()
        mock_gi.repository.GObject = MagicMock()
        mock_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            props = elem_module.GstPyannote.__gproperties__
            assert props["model-name"][0] == str

        finally:
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_speaker_properties_are_integers(self):
        """Test min/max speakers properties are integers."""
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.GstBase = MagicMock()
        mock_gi.repository.GObject = MagicMock()
        mock_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            props = elem_module.GstPyannote.__gproperties__

            assert props["min-speakers"][0] == int
            assert props["max-speakers"][0] == int

            # Check valid ranges
            assert props["min-speakers"][3] >= 0  # Min value >= 0
            assert props["max-speakers"][3] >= 0  # Min value >= 0

        finally:
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_window_duration_is_float(self):
        """Test window-duration property is a float."""
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.GstBase = MagicMock()
        mock_gi.repository.GObject = MagicMock()
        mock_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            props = elem_module.GstPyannote.__gproperties__
            assert props["window-duration"][0] == float
            assert props["window-duration"][3] > 0  # Min value > 0

        finally:
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]

    def test_inference_enabled_is_bool(self):
        """Test inference-enabled property is a boolean."""
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.GstBase = MagicMock()
        mock_gi.repository.GObject = MagicMock()
        mock_gi.repository.GstBase.BaseTransform = type('BaseTransform', (), {})

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module
            import gst_pyannote.element as elem_module

            importlib.reload(pads_module)
            importlib.reload(elem_module)

            props = elem_module.GstPyannote.__gproperties__
            assert props["inference-enabled"][0] == bool

        finally:
            for mod in ['gst_pyannote.element', 'gst_pyannote.pads']:
                if mod in sys.modules:
                    del sys.modules[mod]


@pytest.mark.unit
class TestPadDefinitions:
    """Test pad definitions in pads.py"""

    def test_pad_templates_exist(self):
        """Test that pad templates are defined."""
        mock_gi = MagicMock()
        mock_gi.repository.Gst = MagicMock()
        mock_gi.repository.Gst.Caps.from_string = MagicMock()
        mock_gi.repository.Gst.PadTemplate.new = MagicMock()
        mock_gi.repository.Gst.PadDirection.SINK = 2
        mock_gi.repository.Gst.PadDirection.SRC = 1
        mock_gi.repository.Gst.PadPresence.ALWAYS = 1

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module

            importlib.reload(pads_module)

            # Check templates exist
            assert hasattr(pads_module, 'AUDIO_SINK_TEMPLATE')
            assert hasattr(pads_module, 'AUDIO_SRC_TEMPLATE')
            assert hasattr(pads_module, 'JSON_SRC_TEMPLATE')
            assert hasattr(pads_module, 'CONTROL_SINK_TEMPLATE')

        finally:
            if 'gst_pyannote.pads' in sys.modules:
                del sys.modules['gst_pyannote.pads']

    def test_audio_caps_include_f32le(self):
        """Test audio caps include F32LE format."""
        mock_gi = MagicMock()
        mock_gst = MagicMock()
        mock_gi.repository.Gst = mock_gst

        # Track caps_from_string calls
        caps_calls = []
        mock_gst.Caps.from_string = lambda x: caps_calls.append(x) or MagicMock()
        mock_gst.PadTemplate.new = MagicMock()
        mock_gst.PadDirection.SINK = 2
        mock_gst.PadDirection.SRC = 1
        mock_gst.PadPresence.ALWAYS = 1

        sys.modules['gi'] = mock_gi
        sys.modules['gi.repository'] = mock_gi.repository

        try:
            import importlib
            import gst_pyannote.pads as pads_module

            importlib.reload(pads_module)

            # Check that F32LE was mentioned in caps
            audio_caps = [c for c in caps_calls if 'audio/x-raw' in c]
            assert len(audio_caps) >= 2  # At least sink and src
            assert any('F32LE' in cap for cap in audio_caps)

        finally:
            if 'gst_pyannote.pads' in sys.modules:
                del sys.modules['gst_pyannote.pads']
