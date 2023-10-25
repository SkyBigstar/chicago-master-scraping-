#!/usr/bin/python3

from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<h1>ChicagoCrashes</h1>"


def main():
    app.run()


if __name__ == "__main__":
    main()
