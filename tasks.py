#!/usr/bin/python3

# celery -A tasks worker --loglevel=DEBUG

from datetime import date, datetime, timedelta
import logging
import sys
import random

from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
from celery import Celery, Task
from celery.signals import worker_process_init
import cloudscraper
from dateutil.parser import parse as date_parse
import requests
import redis
import phonenumbers
import pymysql
from lxml import html

from schema import *
from eztexting import *
from justcall import *
from settings import *

CHECK_DAYS = 14
FORM_URL = "https://crash.chicagopolice.org/DriverInformationExchange/driverInfo"
RETRY_AFTER = 5 * 60 # 5 minutes
SQLALCHEMY_URL = "mysql+pymysql://user:C8mMjzDRan7uPzKw3z@localmysql:3306/chicagocrashes"

FRONTIER_SIZE = 2000
MAX_RETRIES_PER_RD = 60 * 24 * 7  # 10080

SITE_KEY = "6LfMvwkTAAAAAPCkEtxBHgi9l8CM2O2j8hiNojTr"

db_session = init_db(SQLALCHEMY_URL)

if "pytest" in sys.argv[0]:
    BROKER_BACKEND = "memory"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    app = Celery("chicagocrashes", broker=BROKER_BACKEND)
    r = None
else:
    redis_url, r = init_redis_conn_and_load_settings()
    init_db(SQLALCHEMY_URL)
    app = Celery("chicagocrashes", broker=redis_url)

DEBUG = False

# http://www.prschmid.com/2013/04/using-sqlalchemy-with-celery-tasks.html
class SqlAlchemyTask(Task):
    """An abstract Celery Task that ensures that the connection the the
    database is closed on task completion"""
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        db_session.remove()

def get_proxy_url():
    username = BRIGHTDATA_ZONE_USERNAME(r)
    password = BRIGHTDATA_ZONE_PASSWORD(r)

    username += "-country-us-session-" + str(random.random())

    proxy_url = "https://{}:{}@brd.superproxy.io:22225".format(username, password)

    return proxy_url


def create_session():
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

    proxy_url = get_proxy_url()
    session.proxies = {"http": proxy_url, "https": proxy_url}

    logging.info("cloudscraper session created")

    return session


session = create_session()

def solve_recaptcha():
    solver = recaptchaV2Proxyless()
    solver.set_verbose(1)
    solver.set_key(ANTICAPTCHA_API_KEY(r))
    solver.set_website_url("https://crash.chicagopolice.org/DriverInformationExchange/home")
    solver.set_website_key(SITE_KEY)

    g_response = solver.solve_and_return_solution()

    if g_response != 0:
        logging.info("reCAPTCHA solved")
        return g_response
    else:
        logging.warn("task finished with error "+solver.error_code)
    
    return None

@app.task(bind=True, base=SqlAlchemyTask, default_retry_delay=RETRY_AFTER, max_retries=65535)
def try_rd_and_date(self, rd, d):
    logging.info("Trying {} {}".format(rd, d.isoformat()))

    accident = db_session.query(Accident).filter(Accident.rd == rd).first()
    if accident is not None:
        logging.warning("Accident {} already listed in DB - dropping task".format(rd))
        r.srem("WATCHED_RDS", rd)
        r.delete(rd)
        return

    captcha_token = solve_recaptcha()
    if captcha_token is not None:
        captcha_token = solve_recaptcha()

    form_data = {
        "g-recaptcha-response": captcha_token,
        "rd": rd,
        "crashDate": d,
    }

    retries = r.incr(rd)

    if not r.sismember("WATCHED_RDS", rd):
        logging.info("{} is not in WATCHED_RDS - dropping the task".format(rd))
        return

    try:
        proxy_url = get_proxy_url()
        proxies = {"http": proxy_url, "https": proxy_url}

        resp = session.post(FORM_URL, proxies=proxies, data=form_data, timeout=3.0)
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        logging.error(repr(e))

        self.retry()
        return

    if "General Crash Information" in resp.text:
        html_str = resp.text

        logging.info("Found crash report {} {}".format(rd, d.isoformat()))
        parse_report_html.delay(html_str)
    elif "Incorrect Crash Date" in resp.text:
        d = d - timedelta(days=1)
        td_from_now = date.today() - d
        if td_from_now.days > CHECK_DAYS:
            r.srem("WATCHED_RDS", rd)
            r.delete(rd)
            return

        logging.info(
            "{} {} Incorrect date - trying one day earlier".format(rd, d.isoformat())
        )
        # https://stackoverflow.com/questions/68915407/celery-retry-with-updated-arguments
        self.retry(args=(rd, d), kwargs={}, countdown=0)
    else:
        logging.info("Crash {} not found - retrying after {} seconds".format(rd, RETRY_AFTER))

        if retries <= MAX_RETRIES_PER_RD:
            self.retry(countdown=RETRY_AFTER)
        else:
            logging.info("Ran out of retries for RD {} - dropping task".format(rd))
            r.srem("WATCHED_RDS", rd)
            r.delete(rd)
            return


def extract_accident_fields(tree):
    accident_dict = dict()

    try:
        accident_dict["address"] = tree.xpath(
            '//dt[text()="Crash Address"]/following-sibling::dd[1]'
        )[0].text
    except:
        pass

    try:
        accident_dict["rd"] = tree.xpath(
            '//dt[text()="Agency Report No."]/following-sibling::dd[1]'
        )[0].text
    except:
        pass

    try:
        accident_dict["date"] = tree.xpath(
            '//dt[text()="Crash Date"]/following-sibling::dd[1]'
        )[0].text
    except:
        pass

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
    return date_parse(date_str).isoformat().split("T")[0]


@app.task(bind=True)
def parse_report_html(self, html_str):
    logging.info("Parsing report HTML")
    logging.debug(html_str)

    tree = html.fromstring(html_str)

    accident_dict = extract_accident_fields(tree)
    unit_dicts = extract_unit_data(tree, accident_dict.get("rd"))

    accident_dict["units"] = unit_dicts

    logging.info("Report {} parsed, will split off the contacts".format(accident_dict.get("rd")))
    split_off_contacts.delay(accident_dict)


def normalise_phone_number(phone_number):
    try:
        pn = phonenumbers.parse(phone_number, "US")
        return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164)
    except:
        return None


def split_name(name):
    try:
        last_name, first_name = name.split(", ")
    except:
        last_name = name
        first_name = ""

    return first_name, last_name


@app.task(bind=True)
def split_off_contacts(self, accident_dict):
    logging.info(
        "Splitting off contacts from report {}".format(accident_dict.get("rd"))
    )

    contacts = []

    crash_date = cleanup_date(accident_dict.get("date"))
    crash_address = accident_dict.get("address")
    at_fault_name = None
    at_fault_phone = None
    at_fault_insurance = None

    for unit_dict in accident_dict.get("units"):
        if unit_dict.get("unit_no") == 1:
            at_fault_name = unit_dict.get("name")
            at_fault_phone = unit_dict.get("phone")
            at_fault_insurance = unit_dict.get("insurance")
            continue

        phone_number = unit_dict.get("driver_phone")
        if phone_number is None:
            continue

        phone_number = normalise_phone_number(phone_number)
        if phone_number is None:
            continue

        if phone_number in PHONE_NUMBER_BLACKLIST(r):
            continue

        first_name, last_name = split_name(unit_dict.get("driver_name"))

        contact = {
            "first_name": first_name,
            "last_name": last_name,
            "rd": unit_dict.get("rd"),
            "unit_no": unit_dict.get("unit_no"),
            "phone_number": phone_number,
            "insurance": unit_dict.get("insurance"),
            "crash_date": crash_date,
            "crash_address": crash_address,
            "at_fault_name": at_fault_name,
            "at_fault_phone": at_fault_phone,
            "at_fault_insurance": at_fault_insurance,
        }

        contacts.append(contact)

    if len(contacts) > 0:
        logging.info(
            "Will message contacts from report {}".format(accident_dict.get("rd"))
        )
        for contact in contacts:
            send_sms_via_eztexting.delay(accident_dict, contact)
    else:
        logging.info(
            "Will export data from report {} to DB".format(accident_dict.get("rd"))
        )
        export_accident_data_to_db(accident_dict)


def cleanup_date(date_str):
    try:
        return date_parse(date_str).date()
    except:
        return None


@app.task(bind=True)
def send_sms_via_eztexting(self, accident_dict, contact):
    logging.info(
        "Sending text message to unit {} from accident {}".format(
            contact.get("unit_no"), contact.get("rd")
        )
    )
    session = create_eztexting_session(EZTEXTING_USERNAME(r), EZTEXTING_PASSWORD(r))

    first_name = contact.get("first_name")
    last_name = contact.get("last_name")
    crash_date = contact.get("crash_date")
    crash_address = contact.get("crash_accident")
    at_fault_name = contact.get("at_fault_name")
    at_fault_phone = contact.get("at_fault_phone")
    at_fault_insurance = contact.get("at_fault_insurance")

    phone = contact.get("phone_number").replace("+1", "")
    note = contact.get("rd") + " " + str(contact.get("unit_no"))

    try:
        add_contact(
            session,
            first_name,
            last_name,
            phone,
            crash_date,
            crash_address,
            at_fault_name,
            at_fault_phone,
            at_fault_insurance,
        )

        send_sms(session, phone, TEMPLATE_ID(r))
    except Exception as e:
        logging.error(repr(e))
        self.retry(countdown=RETRY_AFTER)
        return

    logging.info(
        "Will send the contact ({} unit {}) to JustCall after 1 minute.".format(
            accident_dict.get("rd"), contact.get("unit_no")
        )
    )

    # https://stackoverflow.com/questions/48910214/celery-calling-delay-with-countdown
    export_data_to_justcall.s(accident_dict, contact).apply_async(countdown=60)


# https://justcall.io/developer-docs/#rate_limiting
# 200 per hour = 3.33... per minute
@app.task(bind=True, rate_limit="3/m")
def export_data_to_justcall(self, accident_dict, contact):
    session = create_justcall_session()

    logging.info(
        "Sending contact ({} unit {}) to JustCall".format(
            accident_dict.get("rd"), contact.get("unit_no")
        )
    )

    try:
        push_contact(session, contact)
    except Exception as e:
        logging.error(repr(e))
        self.retry(countdown=RETRY_AFTER)
        return

    if contact.get("exported_at") is None:
        self.retry(countdown=RETRY_AFTER)
        return

    logging.info("Will export accident report {} to DB".format(accident_dict.get("rd")))
    export_accident_data_to_db.delay(accident_dict)
    logging.info(
        "Will export contact {}-{} to DB".format(
            accident_dict.get("rd"), contact.get("unit_no")
        )
    )
    export_contact_data_to_db.delay(accident_dict, contact)


@app.task(bind=True)
def export_accident_data_to_db(self, accident_dict):
    rd = accident_dict.get("rd")
    logging.info(
        "Exporting accident data for {} to database...".format(rd)
    )

    accident = Accident(
        rd=rd,
        address=accident_dict.get("address"),
        date=cleanup_date(accident_dict.get("date")),
        scraped_at=accident_dict.get("scraped_at"),
        exported_at=datetime.now(),
    )
    
    try:
        db_session.add(accident)
        db_session.commit()
    except Exception as e:
        logging.error(repr(e))
        db_session.rollback()

    for unit_dict in accident_dict.get("units", []):
        unit = Unit(
            rd=rd,
            unit_no=unit_dict.get("unit_no"),
            name=unit_dict.get("driver_name"),
            phone_number=unit_dict.get("driver_phone"),
            insurance=unit_dict.get("insurance"),
            address=unit_dict.get("driver_addr"),
            owner_name=unit_dict.get("owner_name"),
            owner_address=unit_dict.get("owner_addr"),
        )

        try:
            db_session.add(unit)
            db_session.commit()
        except Exception as e:
            logging.error(repr(e))
            db_session.rollback()

    r.srem("WATCHED_RDS", rd)
    r.delete(rd)

@app.task(bind=True)
def export_contact_data_to_db(self, accident_dict, contact_dict):
    logging.info(
        "Exporting contact {}-{} to DB...".format(
            contact_dict.get("rd"), contact_dict.get("unit_no")
        )
    )

    contact = Contact(
        rd=contact_dict.get("rd"),
        unit_no=contact_dict.get("unit_no"),
        first_name=contact_dict.get("first_name"),
        last_name=contact_dict.get("last_name"),
        phone_number=contact_dict.get("phone_number"),
        insurance=contact_dict.get("insurance"),
        crash_date=contact_dict.get("crash_date"),
        crash_address=contact_dict.get("crash_address"),
        at_fault_name=contact_dict.get("at_fault_name"),
        at_fault_phone=contact_dict.get("at_fault_phone"),
        at_fault_insurance=contact_dict.get("at_fault_insurance"),
        scraped_at=accident_dict.get("scraped_at"),
        exported_at=contact_dict.get("exported_at"),
    )

    try:
        db_session.add(contact)
        db_session.commit()
    except Exception as e:
        logging.error(repr(e))
        db_session.rollback()

def increment_rd(rd):
    prefix = rd[:2]

    n = int(rd[2:])
    n += 1

    new_rd = prefix + "{:06}".format(n).replace(".0", "")

    return new_rd


def get_initial_rd(db_session):
    fallback_rd = FALLBACK_RD(r)
    fallback_prefix = fallback_rd[:2]

    # https://stackoverflow.com/questions/15791760/how-can-i-do-multiple-order-by-in-flask-sqlalchemy
    last_accident = db_session.query(Accident).order_by(Accident.scraped_at.desc()).first()
    if last_accident is None:
        return fallback_rd

    prefix = last_accident.rd[:2]

    if prefix != fallback_prefix:
        return fallback_rd

    # https://stackoverflow.com/a/47038378
    last_accident2 = (
        db_session.query(Accident).filter(Accident.rd.like(prefix + "%"))
        .order_by(Accident.rd.desc())
        .first()
    )

    rd_idx = int(last_accident2.rd[2:])

    rd_idx -= FRONTIER_SIZE / 2

    initial_rd = prefix + "{:06}".format(rd_idx).replace(".0", "")

    return initial_rd


@app.task(bind=True, base=SqlAlchemyTask)
def update_frontier(self):
    logging.info("Upading frontier")

    cur_frontier_size = r.scard("WATCHED_RDS")
    watched_rds = r.smembers("WATCHED_RDS")
    assert cur_frontier_size == len(watched_rds)

    logging.info("{} RDs currently in frontier".format(cur_frontier_size))
    initial_rd = get_initial_rd(db_session)
    logging.info("Initial RD: {}".format(initial_rd))

    for rd in watched_rds:
        if rd < initial_rd:
            discard_rds.append(rd)
            logging.info("Dropping RD {} from frontier".format(rd))
            r.srem("WATCHED_RDS", rd)

    cur_frontier_size = r.scard("WATCHED_RDS")
    watched_rds = r.smembers("WATCHED_RDS")
    assert cur_frontier_size == len(watched_rds)

    new_rds = []

    if r.scard("WATCHED_RDS") == 0:
        new_rds.append(initial_rd)

        logging.info("Adding RD {} to frontier".format(initial_rd))
        r.sadd("WATCHED_RDS", initial_rd)

        cur_frontier_size = 1

        last_rd = initial_rd
    else:
        watched_rds = list(watched_rds)
        watched_rds = sorted(watched_rds)

        last_rd = watched_rds[-1]

    while FRONTIER_SIZE > r.scard("WATCHED_RDS"):
        last_rd = increment_rd(last_rd)

        accident = db_session.query(Accident).filter(Accident.rd == last_rd).first()
        if accident is not None:
            continue

        new_rds.append(last_rd)
        logging.info("Adding RD {} to frontier".format(last_rd))
        r.sadd("WATCHED_RDS", last_rd)
        r.set(last_rd, 0)

        cur_frontier_size += 1

    if len(new_rds) == 0:
        return

    logging.info("Launching new tasks...")

    today = date.today()

    for new_rd in new_rds:
        logging.info("Launching task {}".format(new_rd))
        try_rd_and_date.delay(new_rd, today)
