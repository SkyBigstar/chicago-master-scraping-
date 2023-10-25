#!/usr/bin/python3

import configparser

import redis

config = dict()


def load_settings(r):
    global config

    config = configparser.ConfigParser()
    config.read("config.ini")

    config = {
        "ANTICAPTCHA_API_KEY": config['ChicagoCrashes']["AntiCaptchaAPIKey"],
        "BRIGHTDATA_ZONE_USERNAME": config["ChicagoCrashes"]["BrightDataZoneUsername"],
        "BRIGHTDATA_ZONE_PASSWORD": config["ChicagoCrashes"]["BrightDataZonePassword"],
        "FALLBACK_RD": config["ChicagoCrashes"]["FallbackRD"],
        "PHONE_NUMBER_BLACKLIST": config["ChicagoCrashes"]["Blacklist"],
        "EZTEXTING_USERNAME": config["ChicagoCrashes"]["EZtextingUsername"],
        "EZTEXTING_PASSWORD": config["ChicagoCrashes"]["EZtextingPassword"],
        "TEMPLATE_ID": config["ChicagoCrashes"]["TemplateID"],
        "FALLBACK_RD": config["ChicagoCrashes"]["FallbackRD"],
        "CAMPAIGN_ID": config["ChicagoCrashes"]["JustCallCampaign"],
        "JUSTCALL_API_KEY": config["ChicagoCrashes"]["JustCallAPIKey"],
        "JUSTCALL_API_SECRET": config["ChicagoCrashes"]["JustCallAPISecret"],
    }

    for key in config.keys():
        value = config[key]

        r.hset("SETTINGS", key, value)


def init_redis_conn():
    config = configparser.ConfigParser()
    config.read("config.ini")

    redis_host = config["ChicagoCrashes"]["RedisHost"]
    redis_port = config["ChicagoCrashes"]["RedisPort"]
    redis_db = int(config["ChicagoCrashes"]["RedisDB"])

    redis_url = "redis://{}:{}/{}".format(redis_host, redis_port, redis_db)

    r = redis.Redis(
        host=redis_host, port=redis_port, db=redis_db, decode_responses=True
    )

    return redis_url, r


def init_redis_conn_and_load_settings():
    redis_url, r = init_redis_conn()

    load_settings(r)

    return redis_url, r

def ANTICAPTCHA_API_KEY(r):
    try:
        return r.hget("SETTINGS", "ANTICAPTCHA_API_KEY")
    except:
        return config.get("ANTICAPTCHA_API_KEY")


def BRIGHTDATA_ZONE_USERNAME(r):
    try:
        return r.hget("SETTINGS", "BRIGHTDATA_ZONE_USERNAME")
    except:
        return config.get("BRIGHTDATA_ZONE_USERNAME")


def BRIGHTDATA_ZONE_PASSWORD(r):
    try:
        return r.hget("SETTINGS", "BRIGHTDATA_ZONE_PASSWORD")
    except:
        return config.get("BRIGHTDATA_ZONE_PASSWORD")


def FALLBACK_RD(r):
    try:
        return r.hget("SETTINGS", "FALLBACK_RD")
    except:
        return config.get("FALLBACK_RD")


def PHONE_NUMBER_BLACKLIST(r):
    try:
        return r.hget("SETTINGS", "PHONE_NUMBER_BLACKLIST").split(",")
    except:
        return config.get("PHONE_NUMBER_BLACKLIST")


def EZTEXTING_USERNAME(r):
    try:
        return r.hget("SETTINGS", "EZTEXTING_USERNAME")
    except:
        return config.get("EZTEXTING_USERNAME")


def EZTEXTING_PASSWORD(r):
    try:
        return r.hget("SETTINGS", "EZTEXTING_PASSWORD")
    except:
        return config.get("EZTEXTING_PASSWORD")


def TEMPLATE_ID(r):
    try:
        return r.hget("SETTINGS", "TEMPLATE_ID")
    except:
        return config.get("TEMPLATE_ID")


def FALLBACK_RD(r):
    try:
        return r.hget("SETTINGS", "FALLBACK_RD")
    except:
        return config.get("FALLBACK_RD")


def CAMPAIGN_ID(r):
    try:
        return r.hget("SETTINGS", "CAMPAIGN_ID")
    except:
        return config.get("CAMPAIGN_ID")


def JUSTCALL_API_KEY(r):
    try:
        return r.hget("SETTINGS", "JUSTCALL_API_KEY")
    except:
        return config.get("JUSTCALL_API_KEY")


def JUSTCALL_API_SECRET(r):
    try:
        return r.hget("SETTINGS", "JUSTCALL_API_SECRET")
    except:
        return config.get("JUSTCALL_API_SECRET")
