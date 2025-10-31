#!/usr/bin/env python
from mysql.connector import Error as MysqlError
from time import sleep
import logging

from amb_client import open_mysql_connection
from amb_client import get_args
from AmbP3.time_server import DecoderTime
from AmbP3.time_client import TimeClient
from AmbP3.time_server import TIME_IP
from AmbP3.time_server import TIME_PORT

# PASSES = [ "db_entry_id", "pass_id", "transponder_id", "rtc_time", "strength", "hits", "flags", "decoder_id" ]
DEFAULT_HEAT_DURATION = 590
DEFAULT_HEAT_COOLDOWN = 90
DEFAULT_HEAT_INTERVAL = 90
DEFAULT_MINIMUM_LAP_TIME = 10
DEFAULT_HEAT_SETTINGS = ["heat_duration", "heat_cooldown"]
MAX_GET_TIME_ATTEMPTS = 30
HEAT_PROCESS_INTERVAL = 0.5  # Heat processing interval in seconds


def is_int(string):
    try:
        int(string)
        return True
    except ValueError:
        return False


def list_to_dict(mylist, index=0):
    "convert a list, tuple into dict by index key"
    foo = {}
    for item in mylist:
        key = item[index]
        values = list(item)
        del values[index]
        foo[key] = values
    return foo


def mysql_connect(conf):
    try:
        con = open_mysql_connection(
            user=conf["mysql_user"],
            db=conf["mysql_db"],
            password=conf["mysql_password"],
            host=conf["mysql_host"],
            port=conf["mysql_port"],
        )
    except MysqlError as err:
        logging.error("Something went wrong: {}".format(err))
    if con is None:
        logging.error("Failed to open DB connection, exiting")
        exit(1)
    else:
        return con
    con.autocommit = True


def sql_write(mycon, query, params=None):
    """Execute a write query with optional parameters.

    Args:
        mycon: Tuple of (mysql_connection, cursor)
        query: SQL query with %s placeholders for parameters
        params: Tuple of parameters to substitute into query (optional)

    Returns:
        Number of affected rows
    """
    mysql = mycon[0]
    cursor = mycon[1]
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    mysql.commit()
    logging.debug(
        "insert query: {}, params: {}, results: {}".format(
            query, params, cursor.rowcount
        )
    )
    return cursor.rowcount


def sql_select(cursor, query, params=None):
    """Execute a select query with optional parameters.

    Args:
        cursor: Database cursor
        query: SQL query with %s placeholders for parameters
        params: Tuple of parameters to substitute into query (optional)

    Returns:
        List of result tuples
    """
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    results = cursor.fetchall()
    logging.debug(
        "select query: {}, params: {}, results: {}".format(
            query, params, cursor.rowcount
        )
    )
    return results


class Pass:
    def __init__(
        self,
        db_entry_id,
        pass_id,
        transponder_id,
        rtc_time,
        strength,
        hits,
        flags,
        decoder_id,
    ):
        self.db_entry_id = db_entry_id
        self.pass_id = pass_id
        self.transponder_id = transponder_id
        self.rtc_time = rtc_time
        self.strength = strength
        self.hits = hits
        self.flags = flags
        self.decoder_id = decoder_id


class Heat:
    def __init__(
        self,
        conf,
        decoder_time,
        heat_duration=DEFAULT_HEAT_DURATION,
        heat_cooldown=DEFAULT_HEAT_COOLDOWN,
        minimum_lap_time=DEFAULT_MINIMUM_LAP_TIME,
        race_flag=0,
    ):
        self.conf = conf
        self.dt = decoder_time
        self.mysql = mysql_connect(conf)
        self.heat_duration = heat_duration
        self.heat_cooldown = heat_cooldown
        self.race_flag = race_flag
        self.minimum_lap_time = minimum_lap_time
        self.cursor = self.mysql.cursor()
        self.mycon = (self.mysql, self.cursor)
        " GET HEAT SETTINGS BEFORE POTENTIALLY CREATING NEW HEAT,"
        query = "select * from settings"
        results = list(sql_select(self.cursor, query))
        if len(results) > 0:
            for result in results:
                setting = result[0]
                setting_value = result[1]
                setting_value = (
                    int(setting_value) if is_int(setting_value) else setting_value
                )
                logging.debug("Found {}: {}".format(setting, setting_value))
                setattr(self, setting, setting_value)
        self.heat = self.get_heat()
        self.heat_id = self.heat[0]
        self.heat_finished = self.heat[1]
        self.first_pass_id = self.heat[2]
        self.last_pass_id = self.heat[3]
        self.rtc_time_start = self.heat[4]
        self.rtc_time_end = self.heat[5]
        self.race_flag = self.heat[6]
        self.rtc_max_duration = self.heat[7]
        if self.rtc_max_duration is None:
            self.rtc_max_duration = self.rtc_time_start + (
                (self.heat_duration + self.heat_cooldown) * 1000000
            )
        if bool(self.first_pass_id) is True:
            self.first_transponder = self.get_transponder(self.first_pass_id)

    def get_heat(self):
        """get's current running heat, if no heat is running will create one"""
        query = (
            "select * from heats where heat_finished=0 order by heat_id desc limit 1"
        )
        result = sql_select(self.cursor, query)
        result_len = len(list(result))
        if result_len > 0:
            heat = result[0]
            logging.debug("Found running heat {}".format(heat))
            return heat
        else:
            self.first_pass_id, self.rtc_time_start, self.rtc_time_end = (
                self.create_heat()
            )
            return self.get_heat()

    def is_running(self, heat_id):
        query = "select heat_finished from heats where heat_id = %s"
        result = sql_select(self.cursor, query, (heat_id,))
        result_len = len(list(result))
        if result_len > 0:
            heat_finished = result[0][0]
        if bool(self.heat_finished) or bool(heat_finished):
            logging.debug("HEAT FINISHED")
            return False
        else:
            return True

    def get_pass_timestamp(self, pass_id):
        return sql_select(
            self.cursor, "select rtc_time from passes where pass_id=%s", (pass_id,)
        )[0][0]

    def get_transponder(self, pass_id):
        query = "select transponder_id from passes where pass_id=%s"
        result = sql_select(self.cursor, query, (pass_id,))[0][0]
        transponder_id = result
        return transponder_id

    def process_heat_passes(self):
        "process heat_passes"
        if bool(self.first_pass_id):
            sleep(HEAT_PROCESS_INTERVAL)
            self.rtc_max_duration = self.rtc_time_start + (
                (self.heat_duration + self.heat_cooldown) * 1000000
            )
            self.first_transponder = self.get_transponder(self.first_pass_id)
            """ FIX ME heat_not_processed_passes_query MUST BE MORE SIMPLE """
            all_heat_passes_query = """select * from passes where pass_id >= %s and rtc_time <= %s
union all ( select * from passes where rtc_time > %s limit 1 )"""
            # nosec B608 - Safe: Formatting is used only to insert a parameterized subquery, not user data
            heat_not_processed_passes_query = """select passes.* from ( {} ) as passes left join laps on
passes.pass_id = laps.pass_id where laps.heat_id is NULL""".format(
                all_heat_passes_query
            )
            #  print(heat_not_processed_passes_query)
            not_processed_passes = sql_select(
                self.cursor,
                heat_not_processed_passes_query,
                (self.first_pass_id, self.rtc_max_duration, self.rtc_max_duration),
            )
            if self.dt.decoder_time > self.rtc_time_end:
                self.wave_finish_flag()
            if self.dt.decoder_time > self.rtc_max_duration:
                self.finish_heat()

            for pas in not_processed_passes:
                pas = Pass(*pas)
                if pas.rtc_time > self.rtc_max_duration:
                    self.finish_heat()
                    break
                else:
                    self.add_pass_to_laps(self.heat_id, pas)
                    if not self.finish_heat and pas.rtc_time > self.rtc_time_end:
                        self.wave_finish_flag()

    def finish_heat(self):
        query = (
            "select pass_id from laps where heat_id=%s order by pass_id desc limit 1"
        )
        result = sql_select(self.cursor, query, (self.heat_id,))
        pass_id = result[0][0] if len(result) > 0 else None
        logging.debug(f"finish heat_id {self.heat_id}, with pass_id: {pass_id}")
        if pass_id is not None:
            query = (
                "update heats set heat_finished=1, last_pass_id=%s where heat_id = %s"
            )
            sql_write(self.mycon, query, (pass_id, self.heat_id))
        else:
            query = (
                "update heats set heat_finished=1, last_pass_id=NULL where heat_id = %s"
            )
            sql_write(self.mycon, query, (self.heat_id,))
        self.heat_finished = 1
        self.heat_flag = 2

    def valid_lap_time(self, pas):
        self.previous_lap_times = {}
        previous_lap_query = """select rtc_time from laps where heat_id=%s
 and transponder_id=%s and pass_id<%s order by pass_id desc limit 1"""

        if pas.transponder_id not in self.previous_lap_times:
            qresult = sql_select(
                self.cursor,
                previous_lap_query,
                (self.heat_id, pas.transponder_id, pas.pass_id),
            )
            if len(qresult) > 0:
                self.previous_lap_times[pas.transponder_id] = qresult[0][0]
            else:
                self.previous_lap_times[pas.transponder_id] = 0

        if (
            pas.rtc_time - self.previous_lap_times[pas.transponder_id]
            > self.minimum_lap_time * 1000000
        ):
            return True
        else:
            query = "delete from passes where pass_id = %s"
            sql_write(self.mycon, query, (pas.pass_id,))
            return False

    def wave_finish_flag(self):
        query = "update  heats set race_flag = 1 where heat_id=%s"
        sql_write(self.mycon, query, (self.heat_id,))
        self.race_flag = 1

    def add_pass_to_laps(self, heat_id, pas):
        lap = {
            "heat_id": heat_id,
            "pass_id": pas.pass_id,
            "transponder_id": pas.transponder_id,
            "rtc_time": pas.rtc_time,
        }
        keys = ", ".join(lap.keys())
        placeholders = ", ".join(["%s"] * len(lap))
        values = tuple(lap.values())
        if self.valid_lap_time(pas):
            # nosec B608 - Safe: keys are hardcoded dict keys, not user input
            query = "insert into laps ({}) values ({})".format(keys, placeholders)
            sql_write(self.mycon, query, values)
        else:
            pass

    def create_heat(self):
        """waits for a new pass and creates a new HEAT
        Parameters:
        mycon: mysql connection and cursor tuple
        heat_duration: create heat with heat_duration

        Returns:
        pass_id: pass id
        rtc_time_start: heat start time
        rtc_time_end: heat end time
        """
        SLEEP_TIME = 1
        cursor = self.mycon[1]

        while True:
            query = "select value from settings where setting = 'green_flag'"
            result = list(sql_select(cursor, query))
            result = result[0][0]
            if len(result) > 0 and bool(int(result)):
                green_flag_time = self.get_decoder_time()
                logging.debug(
                    f"Green Flag is: {result}! Race can start  after: {green_flag_time}"
                )
                break
            else:
                logging.debug("Waiting for Green Flag")
            sleep(SLEEP_TIME)

        while True:
            query = """select * from passes where pass_id > ( select pass_id from laps order by pass_id desc limit 1 )
and rtc_time > %s limit 1"""
            result = sql_select(cursor, query, (green_flag_time,))

            if not len(result) > 0:
                sleep(SLEEP_TIME)
                logging.debug("Waiting on new Pass")
                continue
            else:
                starting_pass = Pass(*result[0])
                self.first_pass_id = starting_pass.pass_id
                self.rtc_time_start = starting_pass.rtc_time
                self.rtc_time_end = self.rtc_time_start + (self.heat_duration * 1000000)
                self.rtc_max_duration = self.rtc_time_start + (
                    (self.heat_duration + self.heat_cooldown) * 1000000
                )
                logging.debug("last pass at {}".format(self.rtc_time_start))
                columns = (
                    "first_pass_id, rtc_time_start, rtc_time_end, rtc_time_max_end"
                )
                values = (
                    self.first_pass_id,
                    self.rtc_time_start,
                    self.rtc_time_end,
                    self.rtc_max_duration,
                )
                logging.debug(
                    f"creating new heat starting starting_pass: {starting_pass.pass_id}, heat_duration: {self.heat_duration}"
                )
                # nosec B608 - Safe: columns is a hardcoded string, not user input
                insert_query = "insert into heats ({}) values (%s, %s, %s, %s)".format(
                    columns
                )
                logging.debug(insert_query)
                if sql_write(self.mycon, insert_query, values) > 0:
                    return starting_pass.pass_id, self.rtc_time_start, self.rtc_time_end

    def check_if_all_finished(self):
        query_number_of_racers = (
            "select count(distinct transponder_id) from laps where heat_id=%s"
        )
        query_number_of_racers_finished = """select count(transponder_id) from laps where heat_id=%s
 and rtc_time > %s"""
        number_of_racers_in_race = sql_select(
            self.cursor, query_number_of_racers, (self.heat_id,)
        )
        number_of_racers_finished = sql_select(
            self.cursor,
            query_number_of_racers_finished,
            (self.heat_id, self.rtc_time_end),
        )
        if (
            len(number_of_racers_in_race) > 0
            and len(number_of_racers_finished) > 0
            and number_of_racers_finished[0][0] >= number_of_racers_in_race[0][0]
        ):
            return True
        else:
            return False

    def run_heat(self):
        logging.debug("RUNNING HEAT")
        current_transponder_time = self.get_decoder_time()
        while self.is_running(self.heat_id):
            if self.race_flag > 0:
                """if race flag is 1 or 2 non-green, check if we are still racing and exit"""
                """ wait for MAX time and the finish teh race """
                if self.race_flag == 2:
                    logging.debug(
                        " #0#0#0#0#0#0 FIRST The race is over, exiting #0#0#0#0#0#0#0#0#)"
                    )
                    break

                if self.check_if_all_finished():
                    logging.debug(
                        " #0#0#0#0#0#0 EVERY ONE FINSIHED The race is over, exiting #0#0#0#0#0#0#0#0#)"
                    )
                    self.finish_heat()
                    break

                if self.get_decoder_time() > self.rtc_max_duration:
                    logging.debug(
                        " #0#0#0#0#0#0 The race is over, exiting #0#0#0#0#0#0#0#0#)"
                    )
                    self.finish_heat()
                    break

            if current_transponder_time > self.rtc_max_duration:
                logging.debug(" #0#0#0#0#0#0 Finish the heat  #0#0#0#0#0#0#0#0#)")
                self.finish_heat()
            else:
                logging.debug(" #0#0#0#0#0#0 processing_passes #0#0#0#0#0#0#0#0#)")
                self.process_heat_passes()

    def get_decoder_time(self):
        while not self.dt.decoder_time:
            sleep(1)
            logging.error("Waiting on time")
        else:
            logging.debug(
                f"################### {self.dt.decoder_time} #####################################"
            )
            return self.dt.decoder_time

    def get_kart_id(self, transponder_id):
        """converts transponder name to kart number and kart name"""
        query = "select name, kart_number from karts where transponder_id = %s"
        result = sql_select(self.cursor, query, (transponder_id,))
        if len(result) == 1:
            return result[0]
        else:
            return transponder_id


def main():
    """IMPLEMENT CONNECT TO CLIENT PYTHON AND GET TIME ALL THE TIME"""
    config = get_args()
    conf = config.conf
    logging.basicConfig(level=logging.DEBUG)
    dt = DecoderTime(0)
    TimeClient(dt, TIME_IP, TIME_PORT)
    while True:
        heat = Heat(conf, decoder_time=dt)
        heat.run_heat()


if __name__ == "__main__":
    main()
