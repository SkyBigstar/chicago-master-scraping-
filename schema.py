#!/usr/bin/python3

import configparser
import sys
import logging
import time

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Date, DateTime, Integer, String, ForeignKey
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import pymysql
pymysql.install_as_MySQLdb()

Base = declarative_base()

# TODO: set up relationships between entities
class Accident(Base):
    __tablename__ = "accident"
    rd = Column(String(8), primary_key=True)
    address = Column(String(16))
    date = Column(Date)
    scraped_at = Column(DateTime)
    exported_at = Column(DateTime)
    
class Unit(Base):
    __tablename__ = "unit"
    rd = Column(String(8), ForeignKey("accident.rd"), primary_key=True)
    unit_no = Column(Integer, primary_key=True)
    name = Column(String(10))
    address = Column(String(10))
    phone_number = Column(String(12))
    insurance = Column(String(10))
    address = Column(String(16))
    owner_name = Column(String(16))
    owner_address = Column(String(16))


class Contact(Base):
    __tablename__ = "contact"
    rd = Column(String(8), primary_key=True)
    unit_no = Column(Integer, primary_key=True)
    first_name = Column(String(10))
    last_name = Column(String(10))
    phone_number = Column(String(12))
    insurance = Column(String(10))
    crash_date = Column(Date)
    crash_address = Column(String(16))
    at_fault_name = Column(String(16))
    at_fault_phone = Column(String(12))
    at_fault_insurance = Column(String(10))
    scraped_at = Column(DateTime)
    exported_at = Column(DateTime)


class ContactLookupStatus(Base):
    __tablename__ = "contact_lookup_status"
    rd = Column(String(8), primary_key=True)
    unit_no = Column(Integer, primary_key=True)
    connectivity_status = Column(String(8))  # XXX: enum?
    info_text = Column(String(32))
    number_type = Column(String(8))  # XXX: enum?
    lookup_done_at = Column(DateTime)


def init_db_impl(sqlalchemy_url):
    logging.info("init_db {}".format(sqlalchemy_url))

    engine = create_engine(sqlalchemy_url)
    db_session = scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=engine)
    )

    logging.info("Initialising database")
    Base.query = db_session.query_property()
    Base.metadata.create_all(bind=engine)
    db_session.commit()
    logging.info("Database initialised")

    return db_session

def init_db(sqlalchemy_url):
    # HACK: keep retrying until connection succeeds

    while True:
        try:
            return init_db_impl(sqlalchemy_url)
        except Exception as e:
            logging.error(e)
            time.sleep(1)

def main():
    if len(sys.argv) == 2:
        sqlalchemy_url = sys.argv[1]
    else:
        sqlalchemy_url = "mysql+pymysql://user:C8mMjzDRan7uPzKw3z@localmysql:3306/chicagocrashes"
    
    db_session = init_db(sqlalchemy_url)
    print(db_session)


if __name__ == "__main__":
    main()

