"""
GStreamer Pyannote Element

Main element implementation for real-time speaker diarization.
"""

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
from gi.repository import GObject, Gst, GstBase

from gst_pyannote.pads import (
    AUDIO_SINK_TEMPLATE,
    AUDIO_SRC_TEMPLATE,
    JSON_SRC_TEMPLATE,
    CONTROL_SINK_TEMPLATE,
)


class GstPyannote(GstBase.BaseTransform):
    """
    GStreamer element for real-time speaker diarization using pyannote-audio.

    This element accepts audio input and provides:
    - Audio pass-through on audio_src pad
    - JSON diarization results on json_src pad
    - Control interface via control_sink pad
    """

    # GStreamer plugin metadata
    __gstmetadata__ = (
        "Pyannote Speaker Diarization",  # Long name
        "Filter/Audio/Analysis",  # Classification
        "Real-time speaker diarization using pyannote-audio",  # Description
        "GStreamer Pyannote Contributors",  # Author
    )

    # Pad templates
    __gsttemplates__ = (
        AUDIO_SINK_TEMPLATE,
        AUDIO_SRC_TEMPLATE,
        JSON_SRC_TEMPLATE,
        CONTROL_SINK_TEMPLATE,
    )

    # GObject properties
    __gproperties__ = {
        "model-name": (
            str,
            "Model Name",
            "Hugging Face model identifier for speaker diarization",
            "pyannote/speaker-diarization-3.1",  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "min-speakers": (
            int,
            "Minimum Speakers",
            "Minimum number of speakers (0 = auto)",
            0,
            100,
            0,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "max-speakers": (
            int,
            "Maximum Speakers",
            "Maximum number of speakers (0 = auto)",
            0,
            100,
            0,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "window-duration": (
            float,
            "Window Duration",
            "Processing window duration in seconds",
            5.0,
            300.0,
            30.0,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "overlap-duration": (
            float,
            "Overlap Duration",
            "Overlap between windows in seconds",
            0.0,
            60.0,
            5.0,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "inference-enabled": (
            bool,
            "Inference Enabled",
            "Enable/disable diarization inference",
            True,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "device": (
            str,
            "Device",
            "PyTorch device (cuda, cpu, cuda:0, etc.)",
            "cuda",  # Default
            GObject.ParamFlags.READWRITE,
        ),
    }

    def __init__(self):
        """Initialize the GstPyannote element."""
        super(GstPyannote, self).__init__()

        # Property values
        self.model_name = "pyannote/speaker-diarization-3.1"
        self.min_speakers = 0
        self.max_speakers = 0
        self.window_duration = 30.0
        self.overlap_duration = 5.0
        self.inference_enabled = True
        self.device = "cuda"

        # Additional pads (beyond the sink/src from BaseTransform)
        # JSON source pad
        self.json_srcpad = Gst.Pad.new_from_template(JSON_SRC_TEMPLATE, "json_src")
        self.add_pad(self.json_srcpad)

        # Control sink pad
        self.control_sinkpad = Gst.Pad.new_from_template(CONTROL_SINK_TEMPLATE, "control_sink")
        self.control_sinkpad.set_event_function_full(self._control_sink_event)
        self.add_pad(self.control_sinkpad)

        # Internal state
        self.pipeline_manager = None  # Will be initialized when needed
        self.audio_buffer = None  # Will be initialized when needed

        # Set element as pass-through by default
        self.set_passthrough(not self.inference_enabled)
        self.set_in_place(True)  # Transform in-place when possible

    def do_get_property(self, prop: GObject.GParamSpec):
        """Get element property value."""
        if prop.name == "model-name":
            return self.model_name
        elif prop.name == "min-speakers":
            return self.min_speakers
        elif prop.name == "max-speakers":
            return self.max_speakers
        elif prop.name == "window-duration":
            return self.window_duration
        elif prop.name == "overlap-duration":
            return self.overlap_duration
        elif prop.name == "inference-enabled":
            return self.inference_enabled
        elif prop.name == "device":
            return self.device
        else:
            raise AttributeError(f"Unknown property: {prop.name}")

    def do_set_property(self, prop: GObject.GParamSpec, value):
        """Set element property value."""
        if prop.name == "model-name":
            self.model_name = value
        elif prop.name == "min-speakers":
            self.min_speakers = value
        elif prop.name == "max-speakers":
            self.max_speakers = value
        elif prop.name == "window-duration":
            self.window_duration = value
        elif prop.name == "overlap-duration":
            self.overlap_duration = value
        elif prop.name == "inference-enabled":
            self.inference_enabled = value
            self.set_passthrough(not value)
        elif prop.name == "device":
            self.device = value
        else:
            raise AttributeError(f"Unknown property: {prop.name}")

    def do_start(self):
        """Called when element transitions to READY state."""
        Gst.info("GstPyannote starting")
        return True

    def do_stop(self):
        """Called when element transitions to NULL state."""
        Gst.info("GstPyannote stopping")
        # Clean up resources
        if self.pipeline_manager:
            # Will implement cleanup later
            pass
        return True

    def do_transform_ip(self, buf: Gst.Buffer):
        """
        Transform buffer in-place.

        For now, this is a simple pass-through. In later phases,
        this will accumulate audio and trigger inference.
        """
        # Pass-through mode: just return OK
        return Gst.FlowReturn.OK

    def _control_sink_event(self, pad: Gst.Pad, parent: Gst.Element, event: Gst.Event):
        """
        Handle events on the control sink pad.

        This will be expanded in Phase 5 to handle control commands.
        """
        if event.type == Gst.EventType.CUSTOM_DOWNSTREAM:
            # Handle custom control events
            Gst.debug(f"Received control event: {event.type}")
            return True
        else:
            # Default event handling
            return Gst.Pad.event_default(pad, parent, event)


# Register element type
GObject.type_register(GstPyannote)
