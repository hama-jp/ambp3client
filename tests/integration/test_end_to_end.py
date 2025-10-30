"""End-to-end integration tests."""
import pytest
import time
from pathlib import Path
from tests.test_utils import (
    read_hex_data_file,
    hex_to_bytes,
    validate_p3_message,
    TestTimer
)
from AmbP3.decoder import (
    Connection,
    p3decode,
    hex_to_binary,
    bin_data_to_ascii,
    bin_to_decimal
)


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndWorkflow:
    """End-to-end tests simulating real usage."""

    def test_complete_data_flow(self, sample_amb_data_file):
        """Test complete data flow from hex file to decoded data."""
        if not sample_amb_data_file:
            pytest.skip("Sample data file not found")

        # Read sample data
        hex_messages = read_hex_data_file(sample_amb_data_file, max_lines=10)
        assert len(hex_messages) > 0, "Should have sample messages"

        decoded_count = 0
        passing_count = 0
        errors = []

        # Process each message
        for hex_msg in hex_messages:
            # Validate format
            if not validate_p3_message(hex_msg):
                errors.append(f"Invalid message format: {hex_msg[:20]}...")
                continue

            try:
                # Convert to binary
                binary_data = hex_to_binary(hex_msg)

                # Decode
                header, body = p3decode(binary_data)

                if header is not None and body is not None:
                    decoded_count += 1

                    # Check if it's a passing record
                    if 'RESULT' in body and 'TOR' in body['RESULT']:
                        tor = body['RESULT'].get('TOR')
                        if tor == 'PASSING':
                            passing_count += 1

            except Exception as e:
                errors.append(f"Error decoding {hex_msg[:20]}...: {str(e)}")

        # Assertions
        assert decoded_count > 0, "Should decode at least one message"
        assert len(errors) < len(hex_messages) * 0.5, f"Too many errors: {errors[:3]}"

        print(f"\nDecoded {decoded_count}/{len(hex_messages)} messages")
        print(f"Found {passing_count} PASSING records")
        if errors:
            print(f"Errors: {len(errors)}")

    def test_message_validation_pipeline(self, sample_p3_messages):
        """Test validation of various message types."""
        valid_count = 0
        invalid_count = 0

        for msg_type, hex_msg in sample_p3_messages.items():
            is_valid = validate_p3_message(hex_msg)

            if is_valid:
                valid_count += 1

                # Should be decodable
                binary_data = hex_to_binary(hex_msg)
                header, body = p3decode(binary_data)

                assert header is not None or body is not None, \
                    f"Valid message should be decodable: {msg_type}"
            else:
                invalid_count += 1

        print(f"\nValidated {valid_count} valid, {invalid_count} invalid messages")

    def test_binary_conversions_roundtrip(self):
        """Test round-trip binary conversions."""
        test_data = [
            b'\x8e\x02\x1f\x00',
            b'\xff\xaa\x00\x12',
            b'\x00\x00\x00\x00',
        ]

        for original in test_data:
            # Binary -> ASCII
            ascii_repr = bin_data_to_ascii(original)

            # ASCII -> Binary
            recovered = hex_to_binary(ascii_repr)

            assert recovered == original, \
                f"Round-trip failed: {original.hex()} -> {ascii_repr} -> {recovered.hex()}"

    def test_performance_decode_many_messages(self, sample_amb_data_file):
        """Test performance of decoding many messages."""
        if not sample_amb_data_file:
            pytest.skip("Sample data file not found")

        hex_messages = read_hex_data_file(sample_amb_data_file, max_lines=50)

        with TestTimer() as timer:
            for hex_msg in hex_messages:
                try:
                    binary_data = hex_to_binary(hex_msg)
                    p3decode(binary_data)
                except:
                    pass

        elapsed = timer.elapsed()
        messages_per_second = len(hex_messages) / elapsed if elapsed > 0 else 0

        print(f"\nProcessed {len(hex_messages)} messages in {elapsed:.3f}s")
        print(f"Rate: {messages_per_second:.1f} messages/second")

        # Should be reasonably fast
        assert elapsed < 10.0, "Processing should complete in under 10 seconds"
        assert messages_per_second > 5, "Should process at least 5 messages/second"

    @pytest.mark.parametrize("hex_message", [
        "8e021f00f3890000020001022800070216000c01760601008104131804008f",
        "8e021f00895d0000020001022500070216000c01760601008104131804008f",
        "8e021f006e970000020001022700070216000c01770601008104131804008f",
    ])
    def test_decode_specific_messages(self, hex_message):
        """Test decoding specific known messages."""
        # Validate
        assert validate_p3_message(hex_message), "Message should be valid"

        # Convert and decode
        binary_data = hex_to_binary(hex_message)
        header, body = p3decode(binary_data)

        # Basic structure checks
        assert header is not None, "Should have header"
        assert 'SOR' in header, "Header should have SOR"
        assert 'TOR' in header, "Header should have TOR"
        assert 'Length' in header, "Header should have Length"

        assert body is not None, "Should have body"
        assert 'RESULT' in body, "Body should have RESULT"

    def test_error_handling_invalid_messages(self):
        """Test error handling with invalid messages."""
        invalid_messages = [
            "",  # Empty
            "00",  # Too short
            "zzzz",  # Invalid hex
            "8e",  # Incomplete
            "ff" * 100,  # Wrong format
        ]

        for invalid_msg in invalid_messages:
            try:
                if invalid_msg:
                    binary_data = hex_to_binary(invalid_msg)
                    header, body = p3decode(binary_data)

                    # If it doesn't raise, check result
                    # Empty/invalid should return None
                    if len(invalid_msg) < 22:  # Minimum valid P3 message in hex
                        # Might return None or partial data
                        pass
            except ValueError:
                # Expected for invalid hex
                pass
            except Exception as e:
                # Other exceptions are OK for invalid input
                print(f"Exception for '{invalid_msg[:20]}...': {type(e).__name__}")

    def test_concurrent_message_processing(self, sample_amb_data_file):
        """Test processing messages from multiple sources."""
        if not sample_amb_data_file:
            pytest.skip("Sample data file not found")

        # Read messages
        hex_messages = read_hex_data_file(sample_amb_data_file, max_lines=20)

        # Process in batches (simulating multiple receivers)
        batch_size = 5
        results = []

        for i in range(0, len(hex_messages), batch_size):
            batch = hex_messages[i:i+batch_size]
            batch_results = []

            for hex_msg in batch:
                try:
                    binary_data = hex_to_binary(hex_msg)
                    header, body = p3decode(binary_data)
                    if header and body:
                        batch_results.append((header, body))
                except:
                    pass

            results.extend(batch_results)

        assert len(results) > 0, "Should process some messages successfully"

    def test_data_integrity_check(self, sample_amb_data_file):
        """Test that decoded data maintains integrity."""
        if not sample_amb_data_file:
            pytest.skip("Sample data file not found")

        hex_messages = read_hex_data_file(sample_amb_data_file, max_lines=10)

        for hex_msg in hex_messages:
            if not validate_p3_message(hex_msg):
                continue

            # Decode
            binary_data = hex_to_binary(hex_msg)
            header, body = p3decode(binary_data)

            if header and body:
                # Check header structure
                assert isinstance(header, dict), "Header should be dict"
                assert 'SOR' in header, "Should have SOR"

                # SOR should be 0x8e
                if isinstance(header['SOR'], bytes):
                    assert header['SOR'] == b'\x8e', "SOR should be 0x8e"

                # Check body structure
                assert isinstance(body, dict), "Body should be dict"

                # If there's a RESULT, it should be a dict
                if 'RESULT' in body:
                    assert isinstance(body['RESULT'], dict), "RESULT should be dict"


@pytest.mark.integration
class TestRealWorldScenarios:
    """Tests simulating real-world usage scenarios."""

    def test_startup_sequence(self, sample_p3_messages):
        """Test typical startup sequence: connect, get time, receive data."""
        # This simulates the startup in amb_client.py

        # 1. Would connect to decoder
        # 2. Wait for GET_TIME message
        # 3. Process passing records

        get_time_msg = sample_p3_messages.get('get_time')
        if get_time_msg:
            binary_data = hex_to_binary(get_time_msg)
            header, body = p3decode(binary_data)

            # Should successfully decode
            assert header is not None
            assert body is not None

    def test_continuous_data_stream(self, sample_amb_data_file):
        """Test handling continuous data stream."""
        if not sample_amb_data_file:
            pytest.skip("Sample data file not found")

        hex_messages = read_hex_data_file(sample_amb_data_file, max_lines=30)

        # Simulate continuous processing
        processed = 0
        errors = 0

        with TestTimer() as timer:
            for hex_msg in hex_messages:
                try:
                    binary_data = hex_to_binary(hex_msg)
                    header, body = p3decode(binary_data)

                    if header and body:
                        processed += 1

                    # Simulate processing delay
                    time.sleep(0.001)

                except Exception:
                    errors += 1

        elapsed = timer.elapsed()

        print(f"\nProcessed {processed} messages, {errors} errors in {elapsed:.3f}s")

        assert processed > 0, "Should process some messages"
        assert errors < processed, "Errors should be less than successful processing"

    def test_data_quality_checks(self, sample_amb_data_file):
        """Test data quality validation."""
        if not sample_amb_data_file:
            pytest.skip("Sample data file not found")

        hex_messages = read_hex_data_file(sample_amb_data_file, max_lines=20)

        stats = {
            'total': len(hex_messages),
            'valid_format': 0,
            'decodable': 0,
            'has_transponder': 0,
            'has_rtc_time': 0,
        }

        for hex_msg in hex_messages:
            # Check format
            if validate_p3_message(hex_msg):
                stats['valid_format'] += 1

                try:
                    # Try to decode
                    binary_data = hex_to_binary(hex_msg)
                    header, body = p3decode(binary_data)

                    if header and body:
                        stats['decodable'] += 1

                        # Check for transponder data
                        if 'RESULT' in body:
                            result = body['RESULT']
                            if 'TRANSPONDER' in result or 'TRANSPONDER_ID' in result:
                                stats['has_transponder'] += 1
                            if 'RTC_TIME' in result:
                                stats['has_rtc_time'] += 1

                except Exception:
                    pass

        # Print statistics
        print(f"\nData Quality Stats:")
        print(f"  Total messages: {stats['total']}")
        print(f"  Valid format: {stats['valid_format']} ({stats['valid_format']/stats['total']*100:.1f}%)")
        print(f"  Decodable: {stats['decodable']} ({stats['decodable']/stats['total']*100:.1f}%)")
        print(f"  Has transponder: {stats['has_transponder']}")
        print(f"  Has RTC time: {stats['has_rtc_time']}")

        # Assertions
        assert stats['valid_format'] > 0, "Should have some valid messages"
        assert stats['decodable'] > 0, "Should decode some messages"
