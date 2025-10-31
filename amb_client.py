#!/usr/bin/env python
from time import sleep
from sys import exit
import os

from AmbP3.config import get_args
from AmbP3.decoder import Connection
from AmbP3.decoder import p3decode
from AmbP3.decoder import bin_data_to_ascii as data_to_ascii
from AmbP3.decoder import bin_dict_to_ascii as dict_to_ascii
from AmbP3.write import Write
from AmbP3.write import open_mysql_connection
from AmbP3.write import Cursor
from AmbP3.time_server import TimeServer
from AmbP3.time_server import DecoderTime
from AmbP3.time_server import RefreshTime


def main():
    print("************ STARTING *******************")
    config = get_args()
    conf = config.conf
    mysql_enabled = conf["mysql_backend"]
    if not mysql_enabled:
        print("ERROR, please configure MySQL")
        exit(1)
    mysql_con = open_mysql_connection(
        user=conf["mysql_user"],
        db=conf["mysql_db"],
        password=conf["mysql_password"],
        host=conf["mysql_host"],
        port=conf["mysql_port"],
    )
    cursor = mysql_con.cursor()
    my_cursor = Cursor(mysql_con, cursor)

    """ start Connection to Decoder """
    connection = Connection(config.ip, config.port)
    connection.connect()
    RefreshTime(connection)

    if not config.file:
        print("file not defined in config")
        exit(1)
    elif not config.debug_file:
        print("debug file not defined in config")
        exit(1)

    # Wait for decoder timestamp with timeout and retry logic
    # These can be configured via environment variables (useful for testing)
    MAX_RETRIES = int(os.getenv("DECODER_TIME_MAX_RETRIES", "30"))
    RETRY_INTERVAL = float(os.getenv("DECODER_TIME_RETRY_INTERVAL", "1.0"))
    decoder_time = None
    retry_count = 0

    while decoder_time is None and retry_count < MAX_RETRIES:
        print(
            f"Waiting for DECODER timestamp (attempt {retry_count + 1}/{MAX_RETRIES})"
        )
        try:
            for data in connection.read():
                decoded_data = data_to_ascii(data)
                decoded_header, decoded_body = p3decode(
                    data
                )  # NEED TO REPLACE WITH LOGGING
                if (
                    decoded_body
                    and "RESULT" in decoded_body
                    and "TOR" in decoded_body["RESULT"]
                ):
                    if "GET_TIME" == decoded_body["RESULT"]["TOR"]:
                        decoder_time = DecoderTime(
                            int(decoded_body["RESULT"]["RTC_TIME"], 16)
                        )
                        print(f"GET_TIME: {decoder_time.decoder_time} Continue")
                        break
        except Exception as e:
            print(f"Error reading decoder time: {e}")
            retry_count += 1
            if retry_count < MAX_RETRIES:
                sleep(RETRY_INTERVAL)
            continue

        if decoder_time is None:
            retry_count += 1
            if retry_count < MAX_RETRIES:
                sleep(RETRY_INTERVAL)

    if decoder_time is None:
        print(f"ERROR: Failed to get decoder time after {MAX_RETRIES} attempts")
        exit(1)

    TimeServer(decoder_time)

    try:
        log_file = config.file
        debug_log_file = config.debug_file
        with open(log_file, "a") as amb_raw, open(debug_log_file, "a") as amb_debug:
            while True:
                raw_log_delim = "##############################################"
                for data in connection.read():
                    decoded_data = data_to_ascii(data)
                    Write.to_file(decoded_data, amb_raw)  # REPLACE BY LOGGING
                    decoded_header, decoded_body = p3decode(
                        data
                    )  # NEED TO REPLACE WITH LOGGING
                    header_msg = "Decoded Header: {}\n".format(
                        dict_to_ascii(decoded_header)
                    )
                    raw_log = f"{raw_log_delim}\n{header_msg}\n{decoded_body}\n"
                    Write.to_file(raw_log, amb_debug)
                    if "TOR" in decoded_body["RESULT"]:
                        if "PASSING" in decoded_body["RESULT"]["TOR"]:
                            Write.passing_to_mysql(my_cursor, decoded_body)
                        elif "RTC_TIME" in decoded_body["RESULT"]["TOR"]:
                            decoder_time.set_decoder_time(
                                int(decoded_body["RESULT"]["RTC_TIME"], 16)
                            )
                sleep(0.2)
    except KeyboardInterrupt:
        print("Closing")
        exit(0)
    except IOError as e:
        print("error writing to file. Reason: {}".format(e))


if __name__ == "__main__":
    main()
