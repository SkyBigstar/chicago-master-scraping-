#!/usr/bin/python3

import configparser
import os
import sys
import logging

from twilio.rest import Client

ACCOUNT_SID = None
AUTH_TOKEN = None
FROM_NUMBER = None


def send_sms(phone_number, contents):
    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    try:
        message = client.messages.create(
            to=phone_number, from_=FROM_NUMBER, body=contents
        )
        logging.info(message)
    except Exception as e:
        logging.error(e)


def main():
    global ACCOUNT_SID
    global AUTH_TOKEN
    global FROM_NUMBER

    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    config = configparser.ConfigParser()
    config.read("send_sms.ini")

    ACCOUNT_SID = config["Twilio"]["AccountSID"]
    AUTH_TOKEN = config["Twilio"]["AuthToken"]
    FROM_NUMBER = config["Twilio"]["FromNumber"]

    log_path = "send_sms.log"

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

    if len(sys.argv) < 2:
        print("Usage:")
        print("{} dst_phone1,dst_phone2,...".format(sys.argv[0]))
        return

    phone_numbers = sys.argv[1].split(",")

    if not os.path.exists("textmsg.txt"):
        logging.error("ERROR: textmsg.txt not found!")
        return

    in_f = open("textmsg.txt", "r")
    contents = in_f.read()
    in_f.close()

    for phone_number in phone_numbers:
        phone_number = phone_number.strip()
        logging.info("Sending message to {}".format(phone_number))
        send_sms(phone_number, contents)


if __name__ == "__main__":
    main()
