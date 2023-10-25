#!/usr/bin/python3

import argparse
from datetime import date, datetime, timedelta
import logging
import os
import sys
import random
from threading import Lock
from multiprocessing.dummy import Pool as ThreadPool

import cloudscraper
from dateutil.parser import parse
import doltcli as dolt
import requests
#from requests.packages.urllib3.exceptions import InsecureRequestWarning
from lxml import html

CHECK_DAYS = 14
LOG_PATH = "scrape.log"
FAKE_TOKEN = "03AGdBq251QqOLEGb78j_ywJ4o-oBfU2SVIiQnefv14NL4NZqn_hRPGA4OLKH2GX6ET7mvHgXVsWdcfB5PTHesTfiB_gowkxa66lkuGZl6_K4VgRXeTZEnNp-ibFnsjAIes39vCzaTP2cV3YtiubpmnLMgJjJKdlbkj66B14QrebVT33wvufbiK-gIFuqCOWo0NHwvbtRmjrkbxD6-DoBUdVPF20j6wf-JUjj6-7hDthCLaabpMrNkZSOKSzy3qQrFXwge1htIAT46Htlv0233sfnQc2FJxdXCEo8PooKW_DBGbDkD-whgZKbZD4NvkGgoHAZEYVeS7dlJBgGdZ2pNggTim-YoMXdX9Sl22Gr26ej3OpMfVl1aGs7ibTUjrQoZ6DwxpzoO4fJ-49B6O33Yp9-IXfcx1us1EmeV8TTSYtJV_QffaIFwPhe73VAkcQhgRWlsJnonl4zYr4Wi-9FyDNXvgxaFhAk18V09F5orplRvtmH5EdRDv_I"

proxy_stats = dict()

mutex = Lock()


def update_proxy_stats(proxy_url, succeeded):
    global proxy_stats

    if proxy_stats.get(proxy_url) is None:
        proxy_stats[proxy_url] = {"total": 0, "succeeded": 0, "failed": 0}

    proxy_stats[proxy_url]["total"] += 1

    if succeeded:
        proxy_stats[proxy_url]["succeeded"] += 1
    else:
        proxy_stats[proxy_url]["failed"] += 1


def setup_logging():
    # Based on:
    # https://stackoverflow.com/a/13733863/1044147
    log_formatter = logging.Formatter(
        "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
    )
    root_logger = logging.getLogger()
    handler1 = logging.FileHandler(LOG_PATH)
    handler1.setFormatter(log_formatter)
    # handler2 = logging.StreamHandler() # XXX: logging to stdout/stderr should probably be disabled due to n8n error on too much logs
    # handler2.setFormatter(log_formatter)

    root_logger.addHandler(handler1)
    # root_logger.addHandler(handler2)

    root_logger.setLevel(logging.DEBUG)


def gen_rd(ref_rd, try_prev, try_next):
    rd_prefix = ref_rd[:2]
    rd_no = int(ref_rd[2:])
    from_rd = rd_no - try_prev
    to_rd = rd_no + try_next

    for i in range(from_rd, to_rd + 1):
        rd = rd_prefix + str(i)
        yield rd


def gen_date():
    today = date.today()
    date_from = today - timedelta(days=14)

    for i in range(CHECK_DAYS + 1):
        d = date_from + timedelta(days=i)
        yield d


def extract_accident_fields(tree):
    accident_dict = dict()

    # XXX: do we need exception handling here?
    accident_dict["address"] = tree.xpath(
        '//dt[text()="Crash Address"]/following-sibling::dd[1]'
    )[0].text
    accident_dict["rd"] = tree.xpath(
        '//dt[text()="Agency Report No."]/following-sibling::dd[1]'
    )[0].text
    accident_dict["date"] = tree.xpath(
        '//dt[text()="Crash Date"]/following-sibling::dd[1]'
    )[0].text
    accident_dict["scraped_at"] = datetime.now()

    return accident_dict


def extract_unit_data(tree, rd):
    unit_dicts = []

    panel_bodies = tree.xpath('//div[@class="panel-body"]')
    if len(panel_bodies) == 0:
        return []

    panel_bodies = panel_bodies[1:]

    for i in range(0, len(panel_bodies)):
        pb = panel_bodies[i]

        unit_no = i + 1

        try:
            driver_name = pb.xpath(
                './/dt[text()="Driver\'s Name"]/following-sibling::dd[1]'
            )[0].text
        except:
            driver_name = ""

        try:
            driver_phone = pb.xpath(
                './/dt[text()="Driver\'s Phone No."]/following-sibling::dd[1]'
            )[0].text
        except:
            driver_phone = ""

        try:
            insurance = pb.xpath(
                './/dt[text()="Insurance Company"]/following-sibling::dd[1]'
            )[0].text
        except:
            insurance = ""

        try:
            driver_addr = pb.xpath(
                './/dt[text()="Driver\'s Address"]/following-sibling::dd[1]'
            )[0].text
        except:
            driver_addr = ""

        try:
            owner_name = pb.xpath(
                './/dt[text()="Owner Name"]/following-sibling::dd[1]'
            )[0].text
        except:
            owner_name = ""

        try:
            owner_addr = pb.xpath(
                './/dt[text()="Owner Address"]/following-sibling::dd[1]'
            )[0].text
        except:
            owner_addr = ""

        unit_dict = {
            "rd": rd,
            "unit_no": unit_no,
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "driver_addr": driver_addr,
            "insurance": insurance,
            "owner_name": owner_name,
            "owner_addr": owner_addr,
            "scraped_at": datetime.now(),
        }

        unit_dicts.append(unit_dict)

    return unit_dicts


def fix_crash_date(date_str):
    return parse(date_str).isoformat().split("T")[0]


# Based on:
# https://github.com/elouajib/sqlescapy/blob/master/sqlescapy/sqlescape.py
def sqlescape(s):
    if s is None:
        return ""

    if type(s) != str:
        return s

    return s.translate(
        s.maketrans(
            {
                "\0": "\\0",
                "\r": "\\r",
                "\x08": "\\b",
                "\x09": "\\t",
                "\x1a": "\\z",
                "\n": "\\n",
                "\r": "\\r",
                '"': "",
                "'": "",
                "\\": "\\\\",
                "%": "\\%",
            }
        )
    )


def get_proxy_dict():
    username = "brd-customer-hl_cecd546c-zone-datacenter_chicagocrashes_ng"
    password = "nnhagpth845j"

    username += "-country-us-session-" + str(random.random())

    proxy_url = "http://{}:{}@brd.superproxy.io:22225".format(username, password)

    return {"http": proxy_url, "https": proxy_url}


def try_scraping_report(session, db, rd, d, disable_proxies):
    logging.info("Trying {} {}...".format(rd, d.isoformat()))

    form_data = {
        "g-recaptcha-response": FAKE_TOKEN,
        "rd": rd,
        "crashDate": d,
    }

    tries_left = 3
    timeout = 2

    resp = None

    while tries_left > 0:
        if not disable_proxies:
            proxies = get_proxy_dict()
        else:
            proxies = None
        try:
            resp = session.post(
                "https://crash.chicagopolice.org/DriverInformationExchange/driverInfo",
                data=form_data,
                proxies=proxies,
                timeout=timeout,
            )
            resp.raise_for_status()
            logging.info(resp.url)
            if not disable_proxies:
                update_proxy_stats(proxies["https"], True)
            break
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            logging.warning(e)
            tries_left -= 1
            if not disable_proxies:
                update_proxy_stats(proxies["https"], False)

            if tries_left == 0:
                logging.error("HTTP POST request failed with error: {}".format(e))
                return

    tree = html.fromstring(resp.text)

    error_p = tree.xpath('//p[contains(@class, "danger")]')
    if len(error_p) > 0:
        error_text = error_p[0].text
        logging.debug(error_text)
        #return error_text.strip() != "Incorrect Crash Date"


    accident_dict = extract_accident_fields(tree)
    unit_dicts = extract_unit_data(tree, accident_dict.get("rd"))

    logging.debug(accident_dict)
    logging.debug(unit_dicts)

    try:
        sql = "INSERT INTO accident (rd, date, address, scraped_at) VALUES ('{}', '{}', '{}', '{}');".format(
            sqlescape(accident_dict.get("rd")),
            fix_crash_date(accident_dict.get("date")),
            sqlescape(accident_dict.get("address")),
            sqlescape(accident_dict.get("scraped_at").isoformat()),
        )

        logging.debug(sql)

        mutex.acquire()
        db.sql(sql)
        mutex.release()
    except Exception as e:
        logging.error(e)
        mutex.release()

    for unit_dict in unit_dicts:
        try:
            sql = "INSERT INTO unit (rd, unit_no, driver_name, driver_phone, driver_addr, insurance, owner_name, owner_addr, scraped_at) VALUES ('{}',  '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}');".format(
                sqlescape(unit_dict.get("rd")),
                unit_dict.get("unit_no"),
                sqlescape(unit_dict.get("driver_name")),
                sqlescape(unit_dict.get("driver_phone")),
                sqlescape(unit_dict.get("driver_addr")),
                sqlescape(unit_dict.get("insurance")),
                sqlescape(unit_dict.get("owner_name")),
                sqlescape(unit_dict.get("owner_addr")),
                sqlescape(unit_dict.get("scraped_at").isoformat()),
            )

            logging.debug(sql)

            mutex.acquire()
            db.sql(sql)
            mutex.release()
        except Exception as e:
            mutex.release()
            logging.error(e)

    return True


def create_session():
    #requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    session = cloudscraper.create_scraper()

    session.headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:98.0) Gecko/20100101 Firefox/98.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Origin": "https://crash.chicagopolice.org",
        "DNT": "1",
        "Connection": "keep-alive",
        "Referer": "https://crash.chicagopolice.org/DriverInformationExchange/home",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Host": "crash.chicagopolice.org",
    }

    return session


def check_rd_presence_in_db(db, rd):
    sql = 'SELECT COUNT(*) FROM `accident` WHERE `rd` = "{}";'.format(rd)
    logging.debug(sql)

    mutex.acquire()
    res = db.sql(sql, result_format="json")
    mutex.release()

    return len(res["rows"]) == 1 and res["rows"][0]["COUNT(*)"] == 1


def check_rd(session, db, rd, disable_proxies):
    for d in gen_date():
        go_to_next_rd = try_scraping_report(session, db, rd, d, disable_proxies)
        if go_to_next_rd:
            break


def traverse_rd_range(db, ref_rd, try_prev, try_next, disable_proxies):
    started_at = datetime.now()
    session = create_session()

    rds_to_check = []

    for rd in gen_rd(ref_rd, try_prev, try_next):
        if check_rd_presence_in_db(db, rd):
            continue

        rds_to_check.append(rd)

    thread_pool = ThreadPool(8)
    thread_pool.map(lambda rd: check_rd(session, db, rd, disable_proxies), rds_to_check)

    finished_at = datetime.now()

    sql = 'INSERT INTO `stats` VALUES ("{}", "{}", "{}", {}, {});'.format(
        started_at, finished_at, ref_rd, try_next, try_prev
    )

    logging.debug(sql)

    mutex.acquire()
    db.sql(sql, result_format="csv")
    mutex.release()

    logging.info("Commiting data to DB")

    db.add(["accident", "unit", "stats"])
    try:
        db.commit(message=datetime.now().isoformat())
    except Exception as e:
        logging.error(e)


def determine_ref_rd(db, yesterday=False):
    if yesterday:
        sql = 'SELECT * FROM `accident` WHERE `scraped_at` < "{} 00:00:00" ORDER BY `rd` DESC LIMIT 1;'.format(
            date.today().isoformat()
        )
    else:
        sql = "SELECT `rd` FROM `accident` ORDER BY `rd` DESC LIMIT 1;"

    logging.debug(sql)

    mutex.acquire()
    res = db.sql(sql, result_format="json")
    mutex.release()

    if len(res["rows"]) == 0:
        logging.error("Reference RD not found; relaunch with --force-start-rd")
        sys.exit(-1)

    return res["rows"][0]["rd"]


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    setup_logging()

    # parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     "--dolt-db-dir", type=str, help="directory for Dolt DB", required=False
    # )
    # parser.add_argument(
    #     "--try-next",
    #     type=int,
    #     help="number of RDs to try after last known one",
    #     default=1000,
    # )
    # parser.add_argument(
    #     "--try-prev",
    #     type=int,
    #     help="number of RDs to try before last known one",
    #     default=1000,
    # )
    # parser.add_argument(
    #     "--force-start-rd", type=str, help="explicit value of initial RD"
    # )
    # parser.add_argument(
    #     "--yesterday",
    #     action="store_true",
    #     default=False,
    #     help="use reference RD from yesterdays data",
    # )
    # parser.add_argument(
    #     "--disable-proxies", action="store_true", default=False, help="disable proxies"
    # )

    # if len(sys.argv) == 1:
    #     parser.print_help()
    #     #return

    # parsed_args = vars(parser.parse_args(sys.argv[1:]))
    

    # db = dolt.Dolt(parsed_args.get("dolt_db_dir"))

    # if parsed_args.get("force_start_rd") is not None:
    #     ref_rd = parsed_args.get("force_start_rd")
    # else:
    #     ref_rd = determine_ref_rd(db, parsed_args.get("yesterday"))

    # logging.info("Reference RD: {}".format(ref_rd))

    db = dolt.Dolt("dolt_db_dir")
    ref_rd ="jg462326"
    try_prev = 1000
    try_next = 1000
    disable_proxies = False

    # traverse_rd_range(
    #     db,
    #     ref_rd,
    #     parsed_args["try_prev"],
    #     parsed_args["try_next"],
    #     parsed_args.get("disable_proxies"),
    # )
    traverse_rd_range(db,ref_rd,try_prev,try_next,False)

    logging.info("Proxy stats: {}".format(proxy_stats))


if __name__ == "__main__":
    main()
