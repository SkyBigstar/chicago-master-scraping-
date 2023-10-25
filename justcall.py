#!/usr/bin/python3

from datetime import datetime
import logging
import json

import requests

from settings import *


def create_justcall_session():
    _, r = init_redis_conn()

    auth = JUSTCALL_API_KEY(r) + ":" + JUSTCALL_API_SECRET(r)

    session = requests.Session()

    session.headers = {"Accept": "application/json", "Authorization": auth}

    return session


def push_contact(session, contact):
    _, r = init_redis_conn()
    first_name = contact.get("first_name")
    last_name = contact.get("last_name")
    phone = contact.get("phone_number")
    note = contact.get("rd") + " " + str(contact.get("unit_no"))

    insurance = contact.get("insurance")
    crash_date = contact.get("crash_date")
    crash_address = contact.get("crash_accident")
    at_fault_name = contact.get("at_fault_name")
    at_fault_phone = contact.get("at_fault_phone")
    at_fault_insurance = contact.get("at_fault_insurance")

    # https://justcall.io/developer-docs/#add_contacts
    json_payload = {
        "campaign_id": CAMPAIGN_ID(r),
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "custom_props": {
            "1107502": contact.get("rd"),
            "1107503": crash_date.isoformat(),
            "1107504": crash_address,
            "1107505": at_fault_name,
            "1107506": at_fault_phone,
            "1107507": at_fault_insurance,
            "1107510": insurance,
        },
    }

    logging.debug(json.dumps(json_payload))

    resp = session.post(
        "https://api.justcall.io/v1/autodialer/campaigns/add", json=json_payload
    )

    logging.debug(resp.text)

    if resp.status_code == 200:
        contact["exported_at"] = datetime.now()
        return
