FROM python:slim-bullseye

ENV TZ="America/Chicago"

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend.py .
COPY eztexting.py .
COPY tasks.py .
COPY schema.py .
COPY justcall.py .
COPY config.ini .
COPY settings.py .

ENTRYPOINT [ "python", "./backend.py" ]
