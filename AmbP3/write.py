from time import time
from sys import exit
from .decoder import bin_to_decimal
from mysql import connector as mysqlconnector
from .logs import Logg

logger = Logg.create_logger("write")

# Database query timeout in seconds
QUERY_TIMEOUT_SECONDS = 300


def open_mysql_connection(
    user, db, password, autocommit=True, host="127.0.0.1", port=3306
):
    try:
        sql_con = mysqlconnector.connect(
            user=user, db=db, password=password, host=host, port=port
        )
        sql_con.autocommit = True
        return sql_con
    except mysqlconnector.errors.ProgrammingError as e:
        logger.error("DB connection failed: {}".format(e))
        return None


def dict_to_sqlquery(data_dict, table):
    columns_string = "( {} )".format(",".join(data_dict.keys()))
    values_string = "( {} )".format(",".join(["%s"] * len(data_dict.values())))
    sql = """INSERT INTO {} {} VALUES {}""".format(table, columns_string, values_string)
    return sql


class Write:
    @staticmethod
    def to_file(data, file_handler):
        if not file_handler.closed:
            try:
                file_handler.write(f"\n{data}")
                file_handler.flush()
            except IOError:
                logger.error("Can not write to {}".format(file_handler.name))
        else:
            logger.error("{} is not a filehandler".format(file_handler))

    @staticmethod
    def passing_to_mysql(my_cursor, result, table="passes"):
        result = result["RESULT"]
        mysql_p3_map = {
            "pass_id": "PASSING_NUMBER",
            "transponder_id": "TRANSPONDER",
            "rtc_time": "RTC_TIME",
            "strength": "STRENGTH",
            "hits": "HITS",
            "flags": "FLAGS",
            "decoder_id": "DECODER_ID",
        }
        mysql_insert = {}
        if "TOR" in result and result["TOR"] == "PASSING":
            for key, value in mysql_p3_map.items():
                if value in result:
                    my_key = key
                    my_value = bin_to_decimal(result[value])
                    mysql_insert[my_key] = my_value
        query = dict_to_sqlquery(mysql_insert, table)
        logger.info("inserting: {}:".format(list(mysql_insert.values())))
        my_cursor.execute(query, list(mysql_insert.values()))


class Cursor(object):
    def __init__(self, db, cursor):
        self.db = db
        self.cursor = cursor
        self.reconnect_counter = 0
        self.time_stamp = int(time())

    def reconnect(self):
        self.reconnect_counter += 1
        if self.reconnect_counter < 10:
            logger.info(
                "Reconnecting to DB. Attempt: {}".format(self.reconnect_counter)
            )
            try:
                self.db.disconnect()
                self.db.reconnect(attempts=30, delay=1)
            except mysqlconnector.errors.OperationalError as e:
                logger.error("ERROR: {}".format(e))
            except (
                mysqlconnector.errors.IntegrityError,
                mysqlconnector.errors.InterfaceError,
            ) as e:
                logger.error("ERROR: {}".format(e))
        else:
            logger.error("Can not connect to DB, exiting")
            exit(1)
        self.cursor = self.db.cursor()

    def execute(self, *args, **kwargs):
        try:
            time_since_last_query = int(time()) - self.time_stamp
            if time_since_last_query < QUERY_TIMEOUT_SECONDS:
                # print("time since last query: {}".format(time_since_last_query))
                # print("autocommit: {}".format(self.db.autocommit))
                result = self.cursor.execute(*args, **kwargs)
                self.time_stamp = int(time())
                self.reconnect_counter = 0
                return result
            else:
                logger.info(
                    "time since last query {} expired".format(time_since_last_query)
                )
                self.reconnect()
                result = self.cursor.execute(*args, **kwargs)
                self.time_stamp = int(time())
                self.reconnect_counter = 0
                return result
        except mysqlconnector.errors.OperationalError as e:
            logger.error("ERROR: {}. RECONNECTING".format(e))
            self.reconnect()
            return self.cursor.execute(*args, **kwargs)
        except (
            mysqlconnector.errors.IntegrityError,
            mysqlconnector.errors.InterfaceError,
        ) as e:
            logger.error("ERROR: {}".format(e))

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
