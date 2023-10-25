#!/usr/bin/python3

import glob
import pickle
import os
import logging
import sys

from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def create_gdrive_service():
    # https://developers.google.com/drive/api/v3/quickstart/python
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    return service


def upload_to_gdrive(filepath):
    # https://developers.google.com/drive/api/v3/manage-uploads
    service = create_gdrive_service()

    file_metadata = {
        "name": os.path.basename(filepath),
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    media = MediaFileUpload(
        filepath,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    remote_file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )

    file_id = remote_file.get("id")

    url = "https://docs.google.com/spreadsheets/d/" + file_id

    perm1 = {"type": "anyone", "role": "reader"}
    service.permissions().create(fileId=file_id, body=perm1, fields="id").execute()
    perm2 = {"type": "user", "role": "writer", "emailAddress": "alawyerhelp@gmail.com"}
    service.permissions().create(fileId=file_id, body=perm2).execute()

    logging.info(url)

    return url


def upload(filepath, filepath2):
    url = upload_to_gdrive(filepath)

    text = "{} {}".format(filepath, url)

    url2 = None
    if filepath2 is not None:
        url2 = upload_to_gdrive(filepath2)
        text += " {} {}".format(filepath2, url2)

    logging.info("Writing to {}: {}".format(filepath, text))

    out_f = open("textmsg.txt", "w")
    out_f.write(text)
    out_f.close()


# FIXME: code duplication with send_clean.py
def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    if len(sys.argv) != 2:
        print("Usage:")
        print("{} <prefix>".format(sys.argv[0]))
        return

    prefix = sys.argv[1]

    log_path = "upload.log"

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

    list_of_files = glob.glob(prefix + "*")

    if len(list_of_files) > 0:
        latest_file = max(list_of_files, key=os.path.getctime)
    else:
        logging.error("No files found with prefix {}".format(prefix))
        sys.exit(1)

    logging.info("Latest file: {}".format(latest_file))

    try:
        upload(latest_file, None)
    except Exception as e:
        logging.error(e)
        sys.exit(2)


if __name__ == "__main__":
    main()
