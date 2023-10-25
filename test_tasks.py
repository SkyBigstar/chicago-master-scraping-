#!/usr/bin/python3

from datetime import date

from tasks import *

import pytest

# https://stackoverflow.com/questions/12078667/how-do-you-unit-test-a-celery-task
@pytest.fixture(scope="module")
def celery_app(request):
    app.conf.update(CELERY_ALWAYS_EAGER=True)
    return app


def test_increment_rd(celery_app):
    testcases = [
        ("JG395217", "JG395218"),
        ("JF000001", "JF000002"),
        ("JE000009", "JE000010"),
    ]

    for from_rd, to_rd in testcases:
        assert increment_rd(from_rd) == to_rd


def test_cleanup_date(celery_app):
    testcases = [("08/29/2023", date(2023, 8, 29)), ("11/11/2021", date(2021, 11, 11))]

    for from_datestr, to_datestr in testcases:
        assert cleanup_date(from_datestr) == to_datestr
