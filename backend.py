#!/usr/bin/python3

import sys

from celery.schedules import crontab

from tasks import app, update_frontier

def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("{} <worker|scheduler>".format(sys.argv[0]))
        return

    choice = sys.argv[1]

    if choice == "worker":
        app.worker_main(["worker", "--loglevel=INFO"])
    elif choice == "scheduler":
        update_frontier.delay()

        app.conf.beat_schedule = {
            "update_frontier_every_minute": {
                "task": "tasks.update_frontier",
                "schedule": 60.0,
            },
        }

        # https://stackoverflow.com/questions/59525048/start-celery-beat-from-a-python-program-without-using-command-line-arguments
        app.Beat(loglevel="info").run()


if __name__ == "__main__":
    main()
