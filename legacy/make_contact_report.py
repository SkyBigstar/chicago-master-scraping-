#!/usr/bin/python3

from datetime import date
import logging
import os
import sys

import doltcli as dolt
import openpyxl

LOG_PATH = "make_contact_report.log"
MAX_UNITS = 6

CONTACT_FIELDNAMES = ["name", "address", "phone", "crash_address", "rd", "date"]


def setup_logging():
    # Based on:
    # https://stackoverflow.com/a/13733863/1044147
    log_formatter = logging.Formatter(
        "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
    )
    root_logger = logging.getLogger()
    handler1 = logging.FileHandler(LOG_PATH)
    handler1.setFormatter(log_formatter)
    handler2 = (
        logging.StreamHandler()
    )  # XXX: logging to stdout/stderr should probably be disabled due to n8n error on too much logs
    handler2.setFormatter(log_formatter)

    root_logger.addHandler(handler1)
    root_logger.addHandler(handler2)

    root_logger.setLevel(logging.DEBUG)


def write_row(ws, row_dict, fieldnames):
    xlsx_row = []

    for f in fieldnames:
        v = row_dict.get(f)
        if v is None:
            v = ""

        xlsx_row.append(v)

    ws.append(xlsx_row)


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    setup_logging()

    if len(sys.argv) != 2:
        print("Usage:")
        print("{} <dolt_db_dir>".format(sys.argv[0]))
        return

    db = dolt.Dolt(sys.argv[1])

    xlsx_filename2 = "contact_{}.xlsx".format(date.today())

    wb2 = openpyxl.Workbook()
    ws2 = wb2.active

    ws2.append(CONTACT_FIELDNAMES)

    sql = "SELECT * FROM `accident` WHERE DATEDIFF(NOW(), `scraped_at`) <= 7;"
    logging.info(sql)

    res = db.sql(sql, result_format="json")
    if res is None or res.get("rows") is None:
        wb2.save(xlsx_filename2)
        return

    for accident_row in res["rows"]:
        rd = accident_row.get("rd")
        crash_address = accident_row.get("address")
        crash_date = accident_row.get("date").split(" ")[0]

        sql2 = 'SELECT * FROM unit WHERE `rd` = "{}";'.format(rd)
        logging.info(sql2)

        try:
            res2 = db.sql(sql2, result_format="json")
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(e)
            continue

        if res2.get("rows") is None:
            continue

        for unit_row in res2["rows"]:
            unit_no = unit_row.get("unit_no")

            contact_row1 = {
                "name": unit_row.get("driver_name"),
                "address": unit_row.get("driver_addr"),
                "phone": unit_row.get("driver_phone"),
                "crash_address": crash_address,
                "rd": rd,
                "date": crash_date,
            }

            write_row(ws2, contact_row1, CONTACT_FIELDNAMES)

            contact_row2 = {
                "name": unit_row.get("owner_name"),
                "address": unit_row.get("owner_addr"),
                "crash_address": crash_address,
                "rd": rd,
                "date": crash_date,
            }

            write_row(ws2, contact_row2, CONTACT_FIELDNAMES)

    wb2.save(xlsx_filename2)


if __name__ == "__main__":
    main()
