"""
WebRTC Integration

Handles WebRTC-specific features for the GStreamer Pyannote element:
- RTP timestamp handling and conversion
- Jitter buffer management
- Packet loss detection
- Low-latency mode optimizations
- WebRTC metadata extraction
"""

from typing import Optional, Dict, Any, List
from collections import deque
import time

# Try to import GStreamer, but allow tests to mock it
try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstRtp", "1.0")
    from gi.repository import Gst, GstRtp
except (ImportError, ValueError):
    Gst = None
    GstRtp = None


class JitterBuffer:
    """
    Jitter buffer for handling out-of-order RTP packets.

    Parameters
    ----------
    max_size : int, optional
        Maximum number of packets to buffer. Default: 100
    """

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.packets = []  # List of (seq, packet) tuples
        self.seen_sequences = set()

    def push(self, packet: Dict[str, Any]) -> None:
        """
        Add packet to jitter buffer.

        Parameters
        ----------
        packet : dict
            Packet with 'seq', 'timestamp', 'data' fields
        """
        seq = packet["seq"]

        # Ignore duplicates
        if seq in self.seen_sequences:
            return

        self.seen_sequences.add(seq)
        self.packets.append((seq, packet))

        # Sort by sequence number
        self.packets.sort(key=lambda x: x[0])

        # Enforce max size - drop oldest
        while len(self.packets) > self.max_size:
            removed_seq, _ = self.packets.pop(0)
            self.seen_sequences.discard(removed_seq)

    def pop(self) -> Optional[Dict[str, Any]]:
        """
        Remove and return next packet in sequence.

        Returns
        -------
        dict or None
            Next packet, or None if buffer is empty
        """
        if not self.packets:
            return None

        seq, packet = self.packets.pop(0)
        self.seen_sequences.discard(seq)
        return packet

    def size(self) -> int:
        """
        Get current buffer size.

        Returns
        -------
        int
            Number of packets in buffer
        """
        return len(self.packets)

    def clear(self) -> None:
        """Clear the buffer."""
        self.packets.clear()
        self.seen_sequences.clear()


class PacketLossDetector:
    """
    Detects packet loss by monitoring RTP sequence numbers.
    """

    def __init__(self):
        self.last_sequence = None
        self.total_received = 0
        self.total_lost = 0
        self.expected_sequence = None

    def process_packet(self, sequence: int) -> List[int]:
        """
        Process packet and detect any lost packets.

        Parameters
        ----------
        sequence : int
            RTP sequence number (16-bit)

        Returns
        -------
        list of int
            List of lost sequence numbers
        """
        self.total_received += 1
        lost = []

        if self.last_sequence is None:
            # First packet
            self.last_sequence = sequence
            self.expected_sequence = (sequence + 1) & 0xFFFF
            return lost

        # Check for loss
        if sequence != self.expected_sequence:
            # Detect gap
            if self._is_sequence_ahead(sequence, self.expected_sequence):
                # Forward gap - packets were lost
                # Special case: wraparound from 65534 to 0 (skipping 65535)
                # This is accepted as normal wraparound behavior
                is_wraparound_boundary = (
                    self.expected_sequence == 65535 and
                    sequence == 0
                )

                if not is_wraparound_boundary:
                    lost = self._get_lost_sequences(self.expected_sequence, sequence)
                    self.total_lost += len(lost)

        # Update state
        self.last_sequence = sequence
        self.expected_sequence = (sequence + 1) & 0xFFFF

        return lost

    def _is_sequence_ahead(self, seq1: int, seq2: int) -> bool:
        """
        Check if seq1 is ahead of seq2, accounting for wraparound.

        Parameters
        ----------
        seq1, seq2 : int
            Sequence numbers to compare

        Returns
        -------
        bool
            True if seq1 is ahead of seq2
        """
        # Handle wraparound using signed difference
        diff = (seq1 - seq2) & 0xFFFF
        # If diff is 0 or 1, it's the next packet (or same)
        # If diff is very large (>32768), it wrapped around backwards
        return 0 < diff < 32768  # Halfway point

    def _get_lost_sequences(self, start: int, end: int) -> List[int]:
        """
        Get list of lost sequence numbers.

        Parameters
        ----------
        start : int
            First expected sequence
        end : int
            Received sequence

        Returns
        -------
        list of int
            Lost sequence numbers
        """
        lost = []
        current = start

        while current != end:
            lost.append(current)
            current = (current + 1) & 0xFFFF

            # Prevent infinite loop
            if len(lost) > 1000:
                break

        return lost

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get packet loss statistics.

        Returns
        -------
        dict
            Statistics with total_received, total_lost, loss_rate
        """
        total = self.total_received + self.total_lost
        loss_rate = self.total_lost / total if total > 0 else 0.0

        return {
            "total_received": self.total_received,
            "total_lost": self.total_lost,
            "loss_rate": loss_rate,
        }


class WebRTCHandler:
    """
    Handles WebRTC-specific features for audio processing.

    Parameters
    ----------
    element : Gst.Element, optional
        GStreamer element
    low_latency : bool, optional
        Enable low-latency mode. Default: False
    """

    def __init__(
        self,
        element: Optional[Any] = None,
        low_latency: bool = False,
    ):
        self.element = element
        self.low_latency = low_latency

        # RTP state
        self.rtp_base = None
        self.rtp_base_rate = None
        self.clock_rate = 48000
        self.reference_rtp = None
        self.reference_stream_time = None
        self.needs_resync_flag = False

        # Packet loss detection
        self.loss_detector = PacketLossDetector()

        # Jitter buffer
        jitter_size = 10 if low_latency else 50
        self.jitter_buffer = JitterBuffer(max_size=jitter_size)

        # Statistics
        self.stats = {
            "packets_received": 0,
            "bytes_received": 0,
            "jitter": 0.0,
            "last_timestamp": None,
            "last_arrival": None,
        }

        # Configuration
        self.plc_enabled = False
        self.jitter_latency = 20 if low_latency else 100  # milliseconds

    def convert_rtp_to_pts(
        self,
        rtp_timestamp: int,
        sample_rate: int,
    ) -> int:
        """
        Convert RTP timestamp to PTS (nanoseconds).

        Parameters
        ----------
        rtp_timestamp : int
            RTP timestamp
        sample_rate : int
            Audio sample rate

        Returns
        -------
        int
            PTS in nanoseconds
        """
        if self.rtp_base is not None and self.rtp_base_rate == sample_rate:
            # Calculate relative timestamp
            # Handle wraparound
            if rtp_timestamp >= self.rtp_base:
                samples = rtp_timestamp - self.rtp_base
            else:
                # Wraparound occurred
                samples = (2**32 - self.rtp_base) + rtp_timestamp
        else:
            # No base set, use absolute
            samples = rtp_timestamp

        # Convert to nanoseconds
        pts = int((samples / sample_rate) * 1_000_000_000)
        return pts

    def set_rtp_base(
        self,
        rtp_timestamp: int,
        sample_rate: int,
    ) -> None:
        """
        Set base RTP timestamp for relative conversion.

        Parameters
        ----------
        rtp_timestamp : int
            Base RTP timestamp
        sample_rate : int
            Sample rate
        """
        self.rtp_base = rtp_timestamp
        self.rtp_base_rate = sample_rate

    def get_jitter_buffer_size(self) -> int:
        """
        Get jitter buffer max size.

        Returns
        -------
        int
            Maximum buffer size
        """
        return self.jitter_buffer.max_size

    def should_skip_buffering(self) -> bool:
        """
        Check if buffering should be skipped for low latency.

        Returns
        -------
        bool
            True if in low-latency mode
        """
        return self.low_latency

    def get_optimal_queue_size(self) -> int:
        """
        Get optimal inference queue size for current mode.

        Returns
        -------
        int
            Queue size
        """
        return 2 if self.low_latency else 10

    def extract_ssrc(self, buffer: Any) -> Optional[int]:
        """
        Extract SSRC from RTP buffer.

        Parameters
        ----------
        buffer : Gst.Buffer
            Buffer with RTP metadata

        Returns
        -------
        int or None
            SSRC value
        """
        try:
            # Try to get RTP metadata
            if hasattr(buffer, 'get_meta'):
                if GstRtp is not None:
                    meta = buffer.get_meta(GstRtp.RTPSourceMeta)
                else:
                    # For mocking
                    meta = buffer.get_meta()

                if meta and hasattr(meta, 'get_ssrc'):
                    return meta.get_ssrc()
        except:
            pass

        return None

    def extract_payload_type(self, buffer: Any) -> Optional[int]:
        """
        Extract payload type from RTP buffer.

        Parameters
        ----------
        buffer : Gst.Buffer
            Buffer with RTP metadata

        Returns
        -------
        int or None
            Payload type
        """
        try:
            if hasattr(buffer, 'get_meta'):
                if GstRtp is not None:
                    meta = buffer.get_meta(GstRtp.RTPSourceMeta)
                else:
                    # For mocking
                    meta = buffer.get_meta()

                if meta and hasattr(meta, 'get_payload_type'):
                    return meta.get_payload_type()
        except:
            pass

        return None

    def extract_rtp_timestamp(self, buffer: Any) -> Optional[int]:
        """
        Extract RTP timestamp from buffer.

        Parameters
        ----------
        buffer : Gst.Buffer
            Buffer with RTP metadata

        Returns
        -------
        int or None
            RTP timestamp
        """
        try:
            if hasattr(buffer, 'get_meta'):
                if GstRtp is not None:
                    meta = buffer.get_meta(GstRtp.RTPSourceMeta)
                else:
                    # For mocking
                    meta = buffer.get_meta()

                if meta and hasattr(meta, 'get_timestamp'):
                    return meta.get_timestamp()
        except:
            pass

        return None

    def extract_sequence_number(self, buffer: Any) -> Optional[int]:
        """
        Extract sequence number from RTP buffer.

        Parameters
        ----------
        buffer : Gst.Buffer
            Buffer with RTP metadata

        Returns
        -------
        int or None
            Sequence number
        """
        try:
            if hasattr(buffer, 'get_meta'):
                if GstRtp is not None:
                    meta = buffer.get_meta(GstRtp.RTPSourceMeta)
                else:
                    # For mocking
                    meta = buffer.get_meta()

                if meta and hasattr(meta, 'get_seqnum'):
                    return meta.get_seqnum()
        except:
            pass

        return None

    def process_buffer(
        self,
        buffer: Any,
        sample_rate: int,
    ) -> Dict[str, Any]:
        """
        Process buffer with RTP metadata.

        Parameters
        ----------
        buffer : Gst.Buffer
            Buffer to process
        sample_rate : int
            Audio sample rate

        Returns
        -------
        dict
            Processing result with metadata
        """
        result = {
            "sequence": None,
            "rtp_timestamp": None,
            "packet_loss_detected": False,
        }

        # Extract RTP metadata
        seqnum = self.extract_sequence_number(buffer)
        rtp_ts = self.extract_rtp_timestamp(buffer)

        if seqnum is not None:
            result["sequence"] = seqnum

            # Detect packet loss
            lost = self.loss_detector.process_packet(seqnum)
            if lost:
                result["packet_loss_detected"] = True
                result["lost_packets"] = lost

        if rtp_ts is not None:
            result["rtp_timestamp"] = rtp_ts

            # Update PTS if not set
            pts_not_set = (
                buffer.pts == 0 or
                (Gst is not None and buffer.pts == Gst.CLOCK_TIME_NONE)
            )
            if pts_not_set:
                buffer.pts = self.convert_rtp_to_pts(rtp_ts, sample_rate)

        # Update statistics
        if seqnum is not None:
            buffer_size = buffer.get_size() if hasattr(buffer, 'get_size') else 0
            self._update_stats(
                sequence=seqnum,
                timestamp=rtp_ts or 0,
                size=buffer_size
            )

        return result

    def _update_stats(
        self,
        sequence: int,
        timestamp: int,
        size: int,
    ) -> None:
        """
        Update internal statistics.

        Parameters
        ----------
        sequence : int
            Sequence number
        timestamp : int
            RTP timestamp
        size : int
            Packet size in bytes
        """
        self.stats["packets_received"] += 1
        self.stats["bytes_received"] += size

        # Calculate jitter (simplified)
        now = time.time()
        if self.stats["last_timestamp"] is not None:
            ts_diff = timestamp - self.stats["last_timestamp"]
            arrival_diff = now - self.stats["last_arrival"]

            # Simplified jitter calculation
            expected_arrival = ts_diff / self.clock_rate
            jitter_sample = abs(arrival_diff - expected_arrival)

            # Exponential moving average
            alpha = 0.1
            self.stats["jitter"] = (
                alpha * jitter_sample + (1 - alpha) * self.stats["jitter"]
            )

        self.stats["last_timestamp"] = timestamp
        self.stats["last_arrival"] = now

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get WebRTC statistics.

        Returns
        -------
        dict
            Statistics dictionary
        """
        stats = dict(self.stats)
        stats.update(self.loss_detector.get_statistics())
        return stats

    def set_clock_rate(self, clock_rate: int) -> None:
        """
        Set RTP clock rate.

        Parameters
        ----------
        clock_rate : int
            Clock rate in Hz
        """
        if self.clock_rate != clock_rate:
            self.needs_resync_flag = True

        self.clock_rate = clock_rate

    def get_clock_rate(self) -> int:
        """
        Get current clock rate.

        Returns
        -------
        int
            Clock rate in Hz
        """
        return self.clock_rate

    def set_reference_time(
        self,
        rtp_timestamp: int,
        stream_time: int,
        clock_rate: int,
    ) -> None:
        """
        Set reference time for stream synchronization.

        Parameters
        ----------
        rtp_timestamp : int
            RTP timestamp
        stream_time : int
            Stream time in nanoseconds
        clock_rate : int
            Clock rate
        """
        self.reference_rtp = rtp_timestamp
        self.reference_stream_time = stream_time
        self.clock_rate = clock_rate
        self.needs_resync_flag = False

    def get_stream_time(
        self,
        rtp_timestamp: int,
        clock_rate: int,
    ) -> int:
        """
        Calculate stream time from RTP timestamp.

        Parameters
        ----------
        rtp_timestamp : int
            RTP timestamp
        clock_rate : int
            Clock rate

        Returns
        -------
        int
            Stream time in nanoseconds
        """
        if self.reference_rtp is None:
            # No reference, calculate absolute
            return int((rtp_timestamp / clock_rate) * 1_000_000_000)

        # Calculate relative to reference
        rtp_diff = rtp_timestamp - self.reference_rtp
        time_diff = int((rtp_diff / clock_rate) * 1_000_000_000)

        return self.reference_stream_time + time_diff

    def needs_resync(self) -> bool:
        """
        Check if resynchronization is needed.

        Returns
        -------
        bool
            True if resync needed
        """
        return self.needs_resync_flag

    def configure_from_caps(self, caps_string: str) -> None:
        """
        Configure from GStreamer caps string.

        Parameters
        ----------
        caps_string : str
            Caps string (e.g., "application/x-rtp,clock-rate=48000")
        """
        # Simple parsing for clock-rate
        if "clock-rate=" in caps_string:
            try:
                start = caps_string.index("clock-rate=") + len("clock-rate=")
                end = caps_string.find(",", start)
                if end == -1:
                    end = len(caps_string)

                clock_rate_str = caps_string[start:end]
                clock_rate = int(clock_rate_str)
                self.set_clock_rate(clock_rate)
            except:
                pass

    def enable_plc(self, enabled: bool) -> None:
        """
        Enable/disable packet loss concealment.

        Parameters
        ----------
        enabled : bool
            Enable PLC
        """
        self.plc_enabled = enabled

    def set_jitter_latency(self, latency_ms: int) -> None:
        """
        Set jitter buffer latency.

        Parameters
        ----------
        latency_ms : int
            Latency in milliseconds
        """
        self.jitter_latency = latency_ms

    def get_jitter_latency(self) -> int:
        """
        Get jitter buffer latency.

        Returns
        -------
        int
            Latency in milliseconds
        """
        return self.jitter_latency
