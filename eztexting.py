#!/usr/bin/python3

import base64
import configparser

import requests


def create_eztexting_session(username, password):
    session = requests.Session()

    session.headers = {
        "Authorization": b"Basic "
        + base64.b64encode((username + ":" + password).encode("ascii")),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    return session


# https://developers.eztexting.com/reference/createorupdateusingpost
def add_contact(
    session,
    first_name,
    last_name,
    phone,
    crash_date,
    crash_address,
    at_fault_name,
    at_fault_phone,
    at_fault_insurance,
):
    json_data = {
        "firstName": first_name,
        "lastName": last_name,
        "phoneNumber": phone,
        # XXX: we hardcode a particular custom field ordering here.
        "custom1": crash_date.isoformat(),
        "custom2": crash_address,
        "custom3": at_fault_name,
        "custom4": at_fault_phone,
        "custom5": at_fault_insurance,
    }

    resp = session.post("https://a.eztexting.com/v1/contacts", json=json_data)
    print(resp.url)
    print(resp.text)

    contact_id = resp.json().get("id")

    return contact_id


# https://developers.eztexting.com/reference/createusingpost_3
def send_sms(session, number, template_id):
    json_data = {"messageTemplateId": template_id, "toNumbers": [number]}

    resp = session.post("https://a.eztexting.com/v1/messages", json=json_data)
    print(resp.url)
    print(resp.text)


def main():
    config = configparser.ConfigParser()
    config.read("config.ini")

    username = config["ChicagoCrashes"]["EZtextingUsername"]
    password = config["ChicagoCrashes"]["EZtextingPassword"]

    session = create_eztexting_session(username, password)

    print(session)
    print(session.headers)
    print(session.cookies)

    contact_id = add_contact(session, "John", "Smith", "5166184624", "test")
    send_sms(session, "5166184624", "63401003")


if __name__ == "__main__":
    main()
