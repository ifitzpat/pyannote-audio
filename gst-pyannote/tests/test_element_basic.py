"""
Phase 1 Tests: Basic GStreamer Element Structure

These tests verify that the GstPyannote element can be created,
has the correct pads, capabilities, and properties.
"""

import pytest


@pytest.mark.unit
class TestElementCreation:
    """Test basic element creation and registration."""

    def test_element_can_be_created(self, gst_init):
        """Test that the pyannote element can be instantiated."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        assert element is not None
        assert isinstance(element, gst_init.Element)

    def test_element_has_correct_name(self, gst_init):
        """Test element factory name."""
        from gst_pyannote.element import GstPyannote

        # Element should be registerable with a specific name
        assert hasattr(GstPyannote, "__gstmetadata__")
        metadata = GstPyannote.__gstmetadata__
        assert "pyannote" in metadata[0].lower() or "diarization" in metadata[0].lower()

    def test_element_metadata(self, gst_init):
        """Test element metadata is properly defined."""
        from gst_pyannote.element import GstPyannote

        metadata = GstPyannote.__gstmetadata__
        assert len(metadata) == 4
        assert isinstance(metadata[0], str)  # Long name
        assert isinstance(metadata[1], str)  # Classification
        assert isinstance(metadata[2], str)  # Description
        assert isinstance(metadata[3], str)  # Author


@pytest.mark.unit
class TestElementPads:
    """Test element pad configuration."""

    def test_element_has_audio_sink_pad(self, gst_init):
        """Test that element has an audio sink pad."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("audio_sink")
        assert pad is not None
        assert pad.get_direction() == gst_init.PadDirection.SINK

    def test_element_has_audio_source_pad(self, gst_init):
        """Test that element has an audio source pad for pass-through."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("audio_src")
        assert pad is not None
        assert pad.get_direction() == gst_init.PadDirection.SRC

    def test_element_has_json_source_pad(self, gst_init):
        """Test that element has a JSON source pad for diarization output."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("json_src")
        assert pad is not None
        assert pad.get_direction() == gst_init.PadDirection.SRC

    def test_element_has_control_sink_pad(self, gst_init):
        """Test that element has a control sink pad."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("control_sink")
        assert pad is not None
        assert pad.get_direction() == gst_init.PadDirection.SINK

    def test_audio_sink_pad_capabilities(self, gst_init, sample_audio_caps):
        """Test audio sink pad accepts correct formats."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("audio_sink")
        caps = pad.get_pad_template_caps()

        # Should accept F32LE audio
        assert caps.can_intersect(sample_audio_caps["f32le_mono_16k"])

    def test_audio_source_pad_capabilities(self, gst_init, sample_audio_caps):
        """Test audio source pad produces correct formats."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("audio_src")
        caps = pad.get_pad_template_caps()

        # Should produce F32LE audio (same as input)
        assert caps.can_intersect(sample_audio_caps["f32le_mono_16k"])

    def test_json_source_pad_capabilities(self, gst_init):
        """Test JSON source pad produces application/json."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        pad = element.get_static_pad("json_src")
        caps = pad.get_pad_template_caps()

        # Should produce application/json
        json_caps = gst_init.Caps.from_string("application/json")
        assert caps.can_intersect(json_caps)


@pytest.mark.unit
class TestElementProperties:
    """Test element properties (GObject properties)."""

    def test_element_has_model_name_property(self, gst_init):
        """Test element has model-name property."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        # Should have model-name property
        assert element.get_property("model-name") is not None

    def test_element_has_min_speakers_property(self, gst_init):
        """Test element has min-speakers property."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        min_speakers = element.get_property("min-speakers")
        assert isinstance(min_speakers, int)
        assert min_speakers >= 0

    def test_element_has_max_speakers_property(self, gst_init):
        """Test element has max-speakers property."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        max_speakers = element.get_property("max-speakers")
        assert isinstance(max_speakers, int)
        assert max_speakers >= 0

    def test_element_has_window_duration_property(self, gst_init):
        """Test element has window-duration property."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        window_duration = element.get_property("window-duration")
        assert isinstance(window_duration, float)
        assert window_duration > 0

    def test_element_has_inference_enabled_property(self, gst_init):
        """Test element has inference-enabled property."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        inference_enabled = element.get_property("inference-enabled")
        assert isinstance(inference_enabled, bool)

    def test_can_set_properties(self, gst_init):
        """Test that properties can be set."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()
        element.set_property("model-name", "pyannote/speaker-diarization-3.1")
        element.set_property("min-speakers", 2)
        element.set_property("max-speakers", 10)
        element.set_property("window-duration", 20.0)
        element.set_property("inference-enabled", False)

        assert element.get_property("model-name") == "pyannote/speaker-diarization-3.1"
        assert element.get_property("min-speakers") == 2
        assert element.get_property("max-speakers") == 10
        assert element.get_property("window-duration") == 20.0
        assert element.get_property("inference-enabled") is False


@pytest.mark.integration
class TestElementInPipeline:
    """Test element behavior in a GStreamer pipeline."""

    def test_element_can_be_linked_to_upstream(self, gst_init, gst_element_factory):
        """Test element can be linked from an audio source."""
        from gst_pyannote.element import GstPyannote

        # Create a simple pipeline: audiotestsrc ! pyannote
        source = gst_element_factory("audiotestsrc")
        convert = gst_element_factory("audioconvert")
        caps_filter = gst_element_factory("capsfilter")

        pyannote = GstPyannote()

        # Set caps for F32LE format
        caps = gst_init.Caps.from_string(
            "audio/x-raw,format=F32LE,rate=16000,channels=1"
        )
        caps_filter.set_property("caps", caps)

        # Link elements
        assert source.link(convert)
        assert convert.link(caps_filter)
        assert caps_filter.link(pyannote)

    def test_element_can_be_linked_to_downstream(self, gst_init, gst_element_factory):
        """Test element audio output can be linked to a sink."""
        from gst_pyannote.element import GstPyannote

        pyannote = GstPyannote()
        sink = gst_element_factory("fakesink")

        # Link audio_src pad to sink
        audio_src_pad = pyannote.get_static_pad("audio_src")
        sink_pad = sink.get_static_pad("sink")
        assert audio_src_pad.link(sink_pad) == gst_init.PadLinkReturn.OK

    def test_json_pad_can_be_linked(self, gst_init, gst_element_factory):
        """Test JSON output pad can be linked to a sink."""
        from gst_pyannote.element import GstPyannote

        pyannote = GstPyannote()
        sink = gst_element_factory("fakesink")

        # Link json_src pad to sink
        json_src_pad = pyannote.get_static_pad("json_src")
        sink_pad = sink.get_static_pad("sink")
        # Note: may require caps negotiation
        link_result = json_src_pad.link(sink_pad)
        assert link_result in [gst_init.PadLinkReturn.OK, gst_init.PadLinkReturn.NOFORMAT]


@pytest.mark.integration
class TestPassThroughMode:
    """Test that audio passes through the element unchanged."""

    def test_audio_passes_through_when_inference_disabled(
        self, gst_init, gst_element_factory
    ):
        """Test audio is forwarded when inference is disabled."""
        from gst_pyannote.element import GstPyannote

        # Create pipeline
        pipeline = gst_init.Pipeline.new("test-pipeline")
        source = gst_element_factory("audiotestsrc")
        convert = gst_element_factory("audioconvert")
        caps_filter = gst_element_factory("capsfilter")
        pyannote = GstPyannote()
        sink = gst_element_factory("fakesink")

        # Configure
        source.set_property("num-buffers", 10)
        source.set_property("samplesperbuffer", 1600)  # 0.1s at 16kHz
        caps = gst_init.Caps.from_string(
            "audio/x-raw,format=F32LE,rate=16000,channels=1"
        )
        caps_filter.set_property("caps", caps)
        pyannote.set_property("inference-enabled", False)

        # Add to pipeline
        pipeline.add(source)
        pipeline.add(convert)
        pipeline.add(caps_filter)
        pipeline.add(pyannote)
        pipeline.add(sink)

        # Link
        assert source.link(convert)
        assert convert.link(caps_filter)
        assert caps_filter.link(pyannote)

        # Link audio_src pad explicitly
        audio_src = pyannote.get_static_pad("audio_src")
        sink_pad = sink.get_static_pad("sink")
        assert audio_src.link(sink_pad) == gst_init.PadLinkReturn.OK

        # Run pipeline briefly
        pipeline.set_state(gst_init.State.PLAYING)

        # Wait for a bit
        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(
            gst_init.SECOND * 2,
            gst_init.MessageType.ERROR | gst_init.MessageType.EOS,
        )

        # Clean up
        pipeline.set_state(gst_init.State.NULL)

        # Should not have errors (EOS or timeout is ok)
        if msg:
            assert msg.type != gst_init.MessageType.ERROR

    def test_element_state_changes(self, gst_init):
        """Test element can transition through states."""
        from gst_pyannote.element import GstPyannote

        element = GstPyannote()

        # Should be able to go to READY
        ret = element.set_state(gst_init.State.READY)
        assert ret != gst_init.StateChangeReturn.FAILURE

        # Should be able to go to PAUSED
        ret = element.set_state(gst_init.State.PAUSED)
        assert ret != gst_init.StateChangeReturn.FAILURE

        # Should be able to go back to NULL
        ret = element.set_state(gst_init.State.NULL)
        assert ret != gst_init.StateChangeReturn.FAILURE
