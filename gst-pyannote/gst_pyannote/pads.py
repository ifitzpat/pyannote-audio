"""
Pad templates for GstPyannote element.

Defines the capabilities and templates for all pads used by the element.
"""

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

# Audio sink pad capabilities
# Accepts F32LE (float32 little-endian) audio at various sample rates
AUDIO_SINK_CAPS = Gst.Caps.from_string(
    "audio/x-raw, "
    "format=(string)F32LE, "
    "rate=(int){8000,16000,22050,32000,44100,48000}, "
    "channels=(int)[1,2], "
    "layout=(string)interleaved"
)

AUDIO_SINK_TEMPLATE = Gst.PadTemplate.new(
    "audio_sink",
    Gst.PadDirection.SINK,
    Gst.PadPresence.ALWAYS,
    AUDIO_SINK_CAPS,
)

# Audio source pad capabilities (pass-through)
# Same as sink - audio passes through unchanged
AUDIO_SRC_CAPS = Gst.Caps.from_string(
    "audio/x-raw, "
    "format=(string)F32LE, "
    "rate=(int){8000,16000,22050,32000,44100,48000}, "
    "channels=(int)[1,2], "
    "layout=(string)interleaved"
)

AUDIO_SRC_TEMPLATE = Gst.PadTemplate.new(
    "audio_src",
    Gst.PadDirection.SRC,
    Gst.PadPresence.ALWAYS,
    AUDIO_SRC_CAPS,
)

# JSON source pad capabilities
# Outputs application/json with diarization results
JSON_SRC_CAPS = Gst.Caps.from_string("application/json")

JSON_SRC_TEMPLATE = Gst.PadTemplate.new(
    "json_src",
    Gst.PadDirection.SRC,
    Gst.PadPresence.ALWAYS,
    JSON_SRC_CAPS,
)

# Control sink pad capabilities
# Accepts custom control messages
CONTROL_SINK_CAPS = Gst.Caps.from_string("application/x-pyannote-control")

CONTROL_SINK_TEMPLATE = Gst.PadTemplate.new(
    "control_sink",
    Gst.PadDirection.SINK,
    Gst.PadPresence.ALWAYS,
    CONTROL_SINK_CAPS,
)
