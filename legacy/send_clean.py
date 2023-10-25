#!/usr/bin/python3

import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import glob
import smtplib
import os
import logging


SMTP_SERVER = None
SMTP_USERNAME = None
SMTP_PASSWORD = None

SMTP_USE_TLS = True
SMTP_DEBUG = True

FROM = None
TO = None


def send_email(subject, text, filepath):
    mail_from = os.environ.get("MAILFROM")
    if mail_from is None:
        mail_from = FROM
    mail_to = os.environ.get("MAILTO")
    if mail_to is None:
        mail_to = TO

    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = subject

    msg.attach(MIMEText(text))
    with open(filepath, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(filepath))

    part["Content-Disposition"] = 'attachment; filename="%s"' % os.path.basename(
        filepath
    )
    msg.attach(part)

    smtp = smtplib.SMTP(SMTP_SERVER, port=2525)
    if SMTP_USE_TLS:
        smtp.starttls()
    if SMTP_DEBUG:
        smtp.set_debuglevel(1)

    smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
    smtp.sendmail(mail_from, mail_to, msg.as_string())
    smtp.quit()
    smtp.close()


def main():
    global SMTP_SERVER
    global SMTP_USERNAME
    global SMTP_PASSWORD
    global FROM
    global TO

    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    config = configparser.ConfigParser()
    config.read("send_clean.ini")

    SMTP_SERVER = config["SMTP"]["Server"]
    SMTP_USERNAME = config["SMTP"]["Username"]
    SMTP_PASSWORD = config["SMTP"]["Password"]
    FROM = config["SMTP"]["From"]
    TO = config["SMTP"]["To"]

    log_path = "send_clean.log"

    # Based on:
    # https://stackoverflow.com/a/13733863/1044147
    log_formatter = logging.Formatter(
        "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
    )
    root_logger = logging.getLogger()
    handler1 = logging.FileHandler(log_path)
    handler1.setFormatter(log_formatter)
    handler2 = logging.StreamHandler()
    handler2.setFormatter(log_formatter)

    root_logger.addHandler(handler1)
    root_logger.addHandler(handler2)

    root_logger.setLevel(logging.DEBUG)

    list_of_files = glob.glob("clean_*.xlsx")
    latest_file = max(list_of_files, key=os.path.getctime)

    logging.info("Latest file: {}".format(latest_file))

    try:
        send_email("New crash report", "New crash report", latest_file)
    except Exception as e:
        logging.error(e)


if __name__ == "__main__":
    main()
