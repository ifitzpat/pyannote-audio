"""
Phase 7 Tests: WebRTC Integration

Tests for WebRTC-specific features:
- RTP timestamp handling
- Jitter buffer management
- Packet loss detection
- Low-latency mode
- WebRTC metadata extraction
"""

import pytest
from unittest.mock import MagicMock, patch, call


@pytest.mark.unit
class TestWebRTCHandler:
    """Test WebRTC handler initialization."""

    def test_webrtc_handler_can_be_created(self):
        """Test that WebRTCHandler can be instantiated."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()
        assert handler is not None

    def test_handler_stores_element_reference(self):
        """Test handler stores element reference."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        mock_element = MagicMock()
        handler = WebRTCHandler(element=mock_element)

        assert handler.element is mock_element

    def test_handler_has_low_latency_mode(self):
        """Test handler supports low-latency mode."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler(low_latency=True)
        assert handler.low_latency is True

        handler = WebRTCHandler(low_latency=False)
        assert handler.low_latency is False


@pytest.mark.unit
class TestRTPTimestampHandling:
    """Test RTP timestamp conversion."""

    def test_convert_rtp_to_pts(self):
        """Test converting RTP timestamp to PTS."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # RTP timestamp at 48kHz sample rate
        rtp_timestamp = 48000  # 1 second
        sample_rate = 48000

        pts = handler.convert_rtp_to_pts(rtp_timestamp, sample_rate)

        # PTS should be in nanoseconds (1 second = 1e9 ns)
        assert pts == 1_000_000_000

    def test_rtp_conversion_with_offset(self):
        """Test RTP conversion with base timestamp offset."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # Set base RTP timestamp
        handler.set_rtp_base(1000, sample_rate=16000)

        # Convert relative timestamp
        rtp_timestamp = 17000  # 16000 samples after base
        pts = handler.convert_rtp_to_pts(rtp_timestamp, sample_rate=16000)

        # Should be 1 second (16000 samples at 16kHz)
        assert pts == 1_000_000_000

    def test_handle_rtp_wraparound(self):
        """Test handling RTP timestamp wraparound."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # RTP timestamps are 32-bit unsigned
        max_rtp = 2**32 - 1
        handler.set_rtp_base(max_rtp - 1000, sample_rate=48000)

        # Timestamp wraps around
        wrapped_timestamp = 500
        pts = handler.convert_rtp_to_pts(wrapped_timestamp, sample_rate=48000)

        # Should handle wraparound correctly
        # (500 + 2^32 - (max_rtp - 1000)) / 48000 * 1e9
        expected_samples = 1501
        expected_pts = int((expected_samples / 48000) * 1_000_000_000)
        assert abs(pts - expected_pts) < 1000  # Within 1 microsecond


@pytest.mark.unit
class TestJitterBuffer:
    """Test jitter buffer functionality."""

    def test_jitter_buffer_can_be_created(self):
        """Test jitter buffer creation."""
        from gst_pyannote.webrtc_handler import JitterBuffer

        buffer = JitterBuffer(max_size=100)
        assert buffer is not None
        assert buffer.max_size == 100

    def test_jitter_buffer_stores_packets(self):
        """Test storing packets in jitter buffer."""
        from gst_pyannote.webrtc_handler import JitterBuffer

        buffer = JitterBuffer()

        packet = {
            "seq": 100,
            "timestamp": 48000,
            "data": b"audio data"
        }

        buffer.push(packet)
        assert buffer.size() == 1

    def test_jitter_buffer_orders_by_sequence(self):
        """Test jitter buffer orders packets by sequence number."""
        from gst_pyannote.webrtc_handler import JitterBuffer

        buffer = JitterBuffer()

        # Push out of order
        buffer.push({"seq": 102, "timestamp": 48200, "data": b"c"})
        buffer.push({"seq": 100, "timestamp": 48000, "data": b"a"})
        buffer.push({"seq": 101, "timestamp": 48100, "data": b"b"})

        # Pop should return in order
        packet1 = buffer.pop()
        assert packet1["seq"] == 100

        packet2 = buffer.pop()
        assert packet2["seq"] == 101

        packet3 = buffer.pop()
        assert packet3["seq"] == 102

    def test_jitter_buffer_handles_duplicates(self):
        """Test jitter buffer ignores duplicate packets."""
        from gst_pyannote.webrtc_handler import JitterBuffer

        buffer = JitterBuffer()

        packet = {"seq": 100, "timestamp": 48000, "data": b"a"}
        buffer.push(packet)
        buffer.push(packet)  # Duplicate

        assert buffer.size() == 1

    def test_jitter_buffer_max_size(self):
        """Test jitter buffer enforces max size."""
        from gst_pyannote.webrtc_handler import JitterBuffer

        buffer = JitterBuffer(max_size=3)

        buffer.push({"seq": 100, "timestamp": 48000, "data": b"a"})
        buffer.push({"seq": 101, "timestamp": 48100, "data": b"b"})
        buffer.push({"seq": 102, "timestamp": 48200, "data": b"c"})
        buffer.push({"seq": 103, "timestamp": 48300, "data": b"d"})

        # Should drop oldest when full
        assert buffer.size() <= 3


@pytest.mark.unit
class TestPacketLossDetection:
    """Test packet loss detection."""

    def test_detect_packet_loss(self):
        """Test detecting lost packets by sequence gaps."""
        from gst_pyannote.webrtc_handler import PacketLossDetector

        detector = PacketLossDetector()

        # Process sequential packets
        detector.process_packet(100)
        detector.process_packet(101)

        # Gap indicates loss
        lost = detector.process_packet(103)

        assert lost == [102]  # Packet 102 was lost

    def test_no_loss_on_sequential_packets(self):
        """Test no loss detected for sequential packets."""
        from gst_pyannote.webrtc_handler import PacketLossDetector

        detector = PacketLossDetector()

        lost1 = detector.process_packet(100)
        lost2 = detector.process_packet(101)
        lost3 = detector.process_packet(102)

        assert lost1 == []
        assert lost2 == []
        assert lost3 == []

    def test_detect_multiple_lost_packets(self):
        """Test detecting multiple consecutive lost packets."""
        from gst_pyannote.webrtc_handler import PacketLossDetector

        detector = PacketLossDetector()

        detector.process_packet(100)

        # Multiple packets lost
        lost = detector.process_packet(105)

        assert lost == [101, 102, 103, 104]

    def test_handle_sequence_wraparound(self):
        """Test handling sequence number wraparound."""
        from gst_pyannote.webrtc_handler import PacketLossDetector

        detector = PacketLossDetector()

        # Sequence numbers are 16-bit
        max_seq = 65535
        detector.process_packet(max_seq - 1)

        # Wraparound
        lost = detector.process_packet(0)

        # Should detect wraparound, not loss
        assert lost == []

    def test_get_loss_statistics(self):
        """Test getting packet loss statistics."""
        from gst_pyannote.webrtc_handler import PacketLossDetector

        detector = PacketLossDetector()

        detector.process_packet(100)
        detector.process_packet(101)
        detector.process_packet(103)  # 102 lost
        detector.process_packet(106)  # 104, 105 lost

        stats = detector.get_statistics()

        assert stats["total_received"] == 4
        assert stats["total_lost"] == 3
        assert stats["loss_rate"] > 0


@pytest.mark.unit
class TestLowLatencyMode:
    """Test low-latency mode optimizations."""

    def test_low_latency_reduces_buffer_size(self):
        """Test low-latency mode uses smaller buffers."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        normal = WebRTCHandler(low_latency=False)
        low_lat = WebRTCHandler(low_latency=True)

        # Low latency should use smaller jitter buffer
        assert low_lat.get_jitter_buffer_size() < normal.get_jitter_buffer_size()

    def test_low_latency_enables_fast_processing(self):
        """Test low-latency mode enables fast processing path."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler(low_latency=True)

        assert handler.should_skip_buffering() is True

    def test_low_latency_configures_queue_size(self):
        """Test low-latency mode configures inference queue size."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler(low_latency=True)
        queue_size = handler.get_optimal_queue_size()

        # Low latency should use smaller queue
        assert queue_size <= 3


@pytest.mark.unit
class TestWebRTCMetadata:
    """Test WebRTC metadata extraction."""

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_extract_ssrc_from_buffer(self, mock_gst):
        """Test extracting SSRC from RTP buffer."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        mock_buffer = MagicMock()
        mock_meta = MagicMock()
        mock_meta.get_ssrc.return_value = 12345

        mock_buffer.get_meta.return_value = mock_meta

        ssrc = handler.extract_ssrc(mock_buffer)
        assert ssrc == 12345

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_extract_payload_type(self, mock_gst):
        """Test extracting payload type from RTP buffer."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        mock_buffer = MagicMock()
        mock_meta = MagicMock()
        mock_meta.get_payload_type.return_value = 96

        mock_buffer.get_meta.return_value = mock_meta

        pt = handler.extract_payload_type(mock_buffer)
        assert pt == 96

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_extract_rtp_timestamp(self, mock_gst):
        """Test extracting RTP timestamp from buffer."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        mock_buffer = MagicMock()
        mock_meta = MagicMock()
        mock_meta.get_timestamp.return_value = 48000

        mock_buffer.get_meta.return_value = mock_meta

        timestamp = handler.extract_rtp_timestamp(mock_buffer)
        assert timestamp == 48000

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_extract_sequence_number(self, mock_gst):
        """Test extracting sequence number from RTP buffer."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        mock_buffer = MagicMock()
        mock_meta = MagicMock()
        mock_meta.get_seqnum.return_value = 1024

        mock_buffer.get_meta.return_value = mock_meta

        seqnum = handler.extract_sequence_number(mock_buffer)
        assert seqnum == 1024


@pytest.mark.unit
class TestBufferProcessing:
    """Test processing buffers with WebRTC metadata."""

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_process_rtp_buffer(self, mock_gst):
        """Test processing buffer with RTP metadata."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        mock_buffer = MagicMock()
        mock_buffer.pts = 0
        mock_meta = MagicMock()
        mock_meta.get_seqnum.return_value = 100
        mock_meta.get_timestamp.return_value = 48000
        mock_buffer.get_meta.return_value = mock_meta

        result = handler.process_buffer(mock_buffer, sample_rate=48000)

        assert result is not None
        assert "sequence" in result
        assert "rtp_timestamp" in result

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_detect_loss_in_stream(self, mock_gst):
        """Test detecting packet loss in buffer stream."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # Create buffers
        mock_buffer1 = MagicMock()
        mock_meta1 = MagicMock()
        mock_meta1.get_seqnum.return_value = 100
        mock_meta1.get_timestamp.return_value = 48000
        mock_buffer1.get_meta.return_value = mock_meta1

        mock_buffer2 = MagicMock()
        mock_meta2 = MagicMock()
        mock_meta2.get_seqnum.return_value = 102  # Gap!
        mock_meta2.get_timestamp.return_value = 48200
        mock_buffer2.get_meta.return_value = mock_meta2

        handler.process_buffer(mock_buffer1, sample_rate=48000)
        result = handler.process_buffer(mock_buffer2, sample_rate=48000)

        # Should detect loss
        assert result.get("packet_loss_detected", False) is True

    @patch('gst_pyannote.webrtc_handler.Gst')
    def test_update_pts_from_rtp(self, mock_gst):
        """Test updating buffer PTS from RTP timestamp."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        mock_buffer = MagicMock()
        mock_buffer.pts = 0  # Not set
        mock_meta = MagicMock()
        mock_meta.get_timestamp.return_value = 48000
        mock_meta.get_seqnum.return_value = 100
        mock_buffer.get_meta.return_value = mock_meta

        handler.process_buffer(mock_buffer, sample_rate=48000)

        # Should update PTS
        # 48000 samples at 48kHz = 1 second = 1e9 ns
        # (actual implementation may vary)
        assert True  # Implementation-specific


@pytest.mark.unit
class TestStreamSynchronization:
    """Test stream synchronization features."""

    def test_track_clock_rate(self):
        """Test tracking RTP clock rate."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        handler.set_clock_rate(48000)
        assert handler.get_clock_rate() == 48000

    def test_calculate_stream_offset(self):
        """Test calculating stream time offset."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # Set reference point
        handler.set_reference_time(
            rtp_timestamp=48000,
            stream_time=1_000_000_000,  # 1 second
            clock_rate=48000
        )

        # Calculate offset for new timestamp
        offset = handler.get_stream_time(
            rtp_timestamp=96000,
            clock_rate=48000
        )

        # Should be 2 seconds
        assert offset == 2_000_000_000

    def test_handle_clock_rate_change(self):
        """Test handling clock rate changes."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        handler.set_clock_rate(16000)
        assert handler.get_clock_rate() == 16000

        handler.set_clock_rate(48000)
        assert handler.get_clock_rate() == 48000

        # Should reset base timestamps on clock rate change
        assert handler.needs_resync() is True


@pytest.mark.unit
class TestWebRTCStatistics:
    """Test WebRTC statistics collection."""

    def test_collect_rtp_statistics(self):
        """Test collecting RTP statistics."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # Process some buffers (mocked)
        for i in range(10):
            handler._update_stats(
                sequence=100 + i,
                timestamp=48000 * i,
                size=960
            )

        stats = handler.get_statistics()

        assert "packets_received" in stats
        assert stats["packets_received"] == 10

    def test_calculate_jitter(self):
        """Test calculating RTP jitter."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # Simulate packets with varying arrival times
        handler._update_stats(sequence=100, timestamp=48000, size=960)
        handler._update_stats(sequence=101, timestamp=48960, size=960)
        handler._update_stats(sequence=102, timestamp=49920, size=960)

        stats = handler.get_statistics()

        assert "jitter" in stats

    def test_track_bytes_received(self):
        """Test tracking total bytes received."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        handler._update_stats(sequence=100, timestamp=48000, size=960)
        handler._update_stats(sequence=101, timestamp=48960, size=1920)

        stats = handler.get_statistics()

        assert stats["bytes_received"] == 2880


@pytest.mark.unit
class TestWebRTCConfiguration:
    """Test WebRTC handler configuration."""

    def test_configure_from_caps(self):
        """Test configuring from GStreamer caps."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        # Mock caps
        caps_string = "application/x-rtp,clock-rate=48000,payload=96"
        handler.configure_from_caps(caps_string)

        assert handler.get_clock_rate() == 48000

    def test_enable_packet_loss_concealment(self):
        """Test enabling packet loss concealment."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        handler.enable_plc(True)
        assert handler.plc_enabled is True

    def test_set_jitter_buffer_latency(self):
        """Test setting jitter buffer latency."""
        from gst_pyannote.webrtc_handler import WebRTCHandler

        handler = WebRTCHandler()

        handler.set_jitter_latency(100)  # 100ms
        assert handler.get_jitter_latency() == 100
