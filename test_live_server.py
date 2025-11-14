#!/usr/bin/env python3
"""
Quick test script for live_test_server.py

Connects to the server and reads a few messages to verify they decode correctly.
"""

import sys
import time
from AmbP3.decoder import Connection, p3decode

def test_live_server(host="127.0.0.1", port=12001, duration=10):
    """Test the live server by connecting and reading messages.

    Args:
        host: Server host
        port: Server port
        duration: How long to read messages (seconds)
    """
    print(f"Connecting to {host}:{port}...")

    conn = Connection(host, port)
    try:
        conn.connect(timeout=5.0)
        print("Connected!")

        start_time = time.time()
        message_count = 0
        passing_count = 0
        status_count = 0
        get_time_count = 0

        while time.time() - start_time < duration:
            messages = conn.read(bufsize=10240)

            for msg_data in messages:
                message_count += 1

                # Decode message
                header, body = p3decode(msg_data, skip_crc_check=False)

                if header is None or body is None:
                    print(f"❌ Failed to decode message #{message_count}")
                    print(f"   Raw data: {msg_data.hex()}")
                    continue

                tor = body.get('RESULT', {}).get('TOR', 'UNKNOWN')

                if tor == 'PASSING':
                    passing_count += 1
                    result = body['RESULT']
                    print(f"✅ PASSING #{passing_count}:")
                    print(f"   Transponder: {result.get('TRANSPONDER', 'N/A')}")
                    print(f"   Strength: {result.get('STRENGTH', 'N/A')}")
                    print(f"   Hits: {result.get('HITS', 'N/A')}")

                elif tor == 'STATUS':
                    status_count += 1
                    result = body['RESULT']
                    print(f"✅ STATUS #{status_count}:")
                    print(f"   Noise: {result.get('NOISE', 'N/A')}")
                    print(f"   Temperature: {result.get('TEMPERATURE', 'N/A')}")
                    print(f"   Voltage: {result.get('INPUT_VOLTAGE', 'N/A')}")

                elif tor == 'GET_TIME':
                    get_time_count += 1
                    result = body['RESULT']
                    print(f"✅ GET_TIME #{get_time_count}:")
                    print(f"   RTC_TIME: {result.get('RTC_TIME', 'N/A')}")

                else:
                    print(f"✅ {tor} message received")

            time.sleep(0.1)

        print("\n" + "="*60)
        print(f"Test completed!")
        print(f"Total messages: {message_count}")
        print(f"  - PASSING: {passing_count}")
        print(f"  - STATUS: {status_count}")
        print(f"  - GET_TIME: {get_time_count}")
        print("="*60)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print("Connection closed")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        duration = int(sys.argv[1])
    else:
        duration = 10

    test_live_server(duration=duration)
