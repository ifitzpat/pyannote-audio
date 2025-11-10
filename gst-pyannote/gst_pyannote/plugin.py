"""
GStreamer plugin registration for pyannote element.

This module handles the registration of the GstPyannote element
with the GStreamer plugin system.
"""

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

# Import the element class to ensure it's registered
from gst_pyannote.element import GstPyannote


def plugin_init(plugin):
    """
    Initialize the plugin.

    This function is called by GStreamer to register the element.

    Args:
        plugin: GstPlugin object

    Returns:
        bool: True if registration succeeded
    """
    type_to_register = GstPyannote

    # Register the element
    return Gst.Element.register(plugin, "pyannote", Gst.Rank.NONE, type_to_register)


# Plugin metadata
__gstelementfactory__ = (
    "pyannote",
    Gst.Rank.NONE,
    GstPyannote,
)
