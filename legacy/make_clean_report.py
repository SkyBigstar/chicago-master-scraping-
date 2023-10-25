#!/usr/bin/python3

import logging
import os
import sys

import doltcli as dolt
import openpyxl

LOG_PATH = "make_clean_report.log"
MAX_UNITS = 6


def get_fieldnames():
    fieldnames = ["rd", "date", "address"]

    for i in range(1, MAX_UNITS + 1):
        fieldnames.append("unit{}_name".format(i))
        fieldnames.append("unit{}_phone".format(i))
        fieldnames.append("unit{}_insurance".format(i))
        fieldnames.append("unit{}_address".format(i))
        fieldnames.append("owner{}_name".format(i))
        fieldnames.append("owner{}_address".format(i))

    return fieldnames


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


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    setup_logging()

    if len(sys.argv) != 2:
        print("Usage:")
        print("{} <dolt_db_dir>".format(sys.argv[0]))
        return

    db = dolt.Dolt(sys.argv[1])

    sql0 = "SELECT HASHOF('HEAD');"
    logging.info(sql0)

    res = db.sql(sql0, result_format="json")
    commit_hash = res.get("rows", [])[0]["HASHOF('HEAD')"]

    xlsx_filename = "clean_{}.xlsx".format(commit_hash[:6])

    wb = openpyxl.Workbook()
    ws = wb.active

    ws.append(get_fieldnames())

    # https://docs.dolthub.com/reference/sql/querying-history#querying-history-using-dolt-system-tables
    sql = "SELECT * FROM `dolt_commit_diff_accident` WHERE to_commit = HASHOF('HEAD') AND from_commit = HASHOF('HEAD~') AND `diff_type` = 'added';"
    logging.info(sql)

    res = db.sql(sql, result_format="json")

    for accident_row in res.get("rows", []):
        rd = None
        crash_address = None
        crash_date = None

        for column in accident_row.keys():
            if column.startswith("from_"):
                continue

            if column == "to_rd":
                rd = accident_row.get(column)

            if column == "to_address":
                crash_address = accident_row.get(column)

            if column == "to_date":
                crash_date = accident_row.get(column).split(" ")[0]

        if rd is None:
            continue

        sql2 = 'SELECT * FROM unit WHERE `rd` = "{}";'.format(rd)
        logging.info(sql2)

        try:
            res2 = db.sql(sql2, result_format="json")
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(e)
            continue

        out_row = {"rd": rd, "address": crash_address, "date": crash_date}

        for unit_row in res2.get("rows", []):
            unit_no = unit_row.get("unit_no")
            out_row["unit{}_name".format(unit_no)] = unit_row.get("driver_name")
            out_row["unit{}_phone".format(unit_no)] = unit_row.get("driver_phone")
            out_row["unit{}_address".format(unit_no)] = unit_row.get("driver_addr")
            out_row["unit{}_insurance".format(unit_no)] = unit_row.get("insurance")
            out_row["owner{}_name".format(unit_no)] = unit_row.get("owner_name")
            out_row["owner{}_address".format(unit_no)] = unit_row.get("owner_addr")

        xlsx_row = []

        for f in get_fieldnames():
            v = out_row.get(f)
            if v is None:
                v = ""

            xlsx_row.append(v)

        ws.append(xlsx_row)

    wb.save(filename=xlsx_filename)
    print(xlsx_filename)


if __name__ == "__main__":
    main()
