from flask import Flask
import sqlite3
from flask import request, abort, jsonify, g
import uuid
import datetime
import hmac
import sys
import os
import json
import atexit
import math
from flask_cors import CORS

from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config["NUMBER_OF_PROXIES"] = 2
app.config["SECRET"] = b"Burritos are my favorite animal"
app.config["DATABASE"] = "backend/yoda.db"
app.config["HIGHSCORE_FILE"] = "highscores.txt"

app.config.from_envvar("YODASPIN_SETTINGS")

CORS(app)
VERSION = "1"

# Security related stuff
MAX_CONTENT_LENGTH = 300

# The following constants must be kept in sync with the client
DEGREES_PER_INTERVAL = 4
SPIN_TIMER_INTERVAL_MS = 32
SPINS_BETWEEN_UPDATES = 13
MINIMUM_INITIAL_SPINS_FOR_REGISTRATION = SPINS_BETWEEN_UPDATES
MAXIMUM_INITIAL_SPINS_FOR_REGISTRATION = 2 * SPINS_BETWEEN_UPDATES

TIME_FOR_ONE_SPIN_MS = (360 / DEGREES_PER_INTERVAL) * 32
EXPECTED_TIME_BETWEEN_UPDATES_MS = SPINS_BETWEEN_UPDATES * TIME_FOR_ONE_SPIN_MS
EXPECTED_TIME_BETWEEN_UPDATES_S = EXPECTED_TIME_BETWEEN_UPDATES_MS / 1000
MAXIMUM_TIME_BETWEEN_UPDATES_S = EXPECTED_TIME_BETWEEN_UPDATES_S * 5


def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value) for idx, value in enumerate(row))


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = make_dicts
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.commit()
        db.close()


@app.errorhandler(500)
@app.errorhandler(401)
@app.errorhandler(413)
@app.errorhandler(403)
@app.errorhandler(400)
@app.errorhandler(422)
def handle_too_long(e):
    return jsonify(error=str(e)), e.code


@app.route("/", methods=["GET"])
def status():
    return "itsworkinganakin.gif"


@app.route(f"/v{VERSION}/leaderboard", methods=["GET"])
def leaderboard():
    return "Jayden is winning!"


def sanity_checks():
    if request.content_length > MAX_CONTENT_LENGTH:
        abort(413, description="Too much for me buddy")

    if not request.is_json:
        abort(400, "Bro can you even")


def get_ip_from_request():
    if app.debug:
        return request.remote_addr

    forward_chain = request.headers.getlist("X-Forwarded-For")

    if len(forward_chain) < app.config["NUMBER_OF_PROXIES"]:
        abort(403, "Nice try hackerman")

    # todo: configure nginx to only accept requests from cloudflare?
    user_ip = forward_chain[-1 * app.config["NUMBER_OF_PROXIES"]]
    return user_ip


def get_secret_hash(timestamp, addr, client_id, spins):
    """
    timestamp: int
    addr: string
    client_id: byte string
    spins: int
    """
    m = bytearray()
    m.extend(timestamp.to_bytes(4, sys.byteorder))
    m.extend(spins.to_bytes(16, sys.byteorder))
    m.extend(addr)
    m.extend(client_id)

    return hmac.digest(app.config["SECRET"], m, "MD5")


@app.route(f"/v{VERSION}/register", methods=["POST"])
def register():
    sanity_checks()
    body = request.json
    if "spins" not in body or type(body["spins"]) != int:
        abort(400, "Learn to code")
    spins = int(body["spins"])

    # we return to the client an HMAC of
    # (1) their IP
    # (2) a timestamp
    # (3) a uuid we generate
    # (4) the current number of spins (bounded)
    # The client then uses this has hash as a token when they go to do an update
    # The server saves no state until the client decides its on the leaderboard
    # and starts hitting the updateleaderboard endpoint instead of the update endpoint
    addr = get_ip_from_request()
    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    id = uuid.uuid4()

    if (
        spins < MINIMUM_INITIAL_SPINS_FOR_REGISTRATION
        or spins > MAXIMUM_INITIAL_SPINS_FOR_REGISTRATION
    ):
        abort(401, "Trying to pull a fast one?")

    token = get_secret_hash(timestamp, bytes(addr, "ascii"), id.bytes, spins)

    return jsonify({"timestamp": timestamp, "id": id, "token": token.hex()})


@app.route(f"/v{VERSION}/update", methods=["POST"])
def update():
    # sanity checks
    sanity_checks()
    body = request.json

    # quick and dirty schema validation
    if (
        "id" not in body
        or "previous-spins" not in body
        or "spins" not in body
        or "token" not in body
        or "timestamp" not in body
    ):
        abort(400, "Learn to code")

    previous_spins = body["previous-spins"]
    spins = body["spins"]
    old_timestamp = body["timestamp"]
    id = body["id"]
    token = body["token"]

    if (
        type(previous_spins) != int
        or type(old_timestamp) != int
        or type(spins) != int
        or type(token) != str
        or type(id) != str
    ):
        abort(400, "That doesn't go there")

    id = uuid.UUID(id)
    token = bytearray.fromhex(token)

    addr = get_ip_from_request()

    calculated_token = get_secret_hash(
        old_timestamp,
        bytes(addr, "ascii"),
        id.bytes,
        previous_spins,
    )

    if not hmac.compare_digest(calculated_token, token):
        abort(401, "You lied to me")

    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    # the soonest they are allowed to check in again
    # earliest_checkin = old_timestamp + EXPECTED_TIME_BETWEEN_UPDATES_S

    # the latest after their last token was issued they can check in again
    latest_checkin = old_timestamp + MAXIMUM_TIME_BETWEEN_UPDATES_S

    # if timestamp < earliest_checkin:
    #    abort(403, f"Too soon ({timestamp} / {earliest_checkin}")

    if timestamp > latest_checkin:
        abort(403, f"Too late")

    # calculate what we would expect them to increment by based off of the time
    # delta

    delta = timestamp - old_timestamp

    # TODO: make sure rounding here isn't causing any exploits
    expected_spins = round(previous_spins + delta / (TIME_FOR_ONE_SPIN_MS / 1000))

    if expected_spins < spins:
        # they went too fast
        abort(403, f"Cool your jets {expected_spins} / {spins}")

    # we allow them to go slower than expected, as long as they are in the MAXIMUM_TIME_BETWEEN_UPDATES_S window

    # at this point, the hash (and therfore the spin count) they gave is correct
    # and the timing is correct. issue a new token
    new_token = get_secret_hash(timestamp, bytes(addr, "ascii"), id.bytes, spins)

    return jsonify(
        {
            "timestamp": timestamp,
            "token": new_token.hex(),
        }
    )


@app.route(f"/v{VERSION}/updateleaderboard", methods=["POST"])
def updateleaderboard():
    response = update()

    # at this point, we have authenticated the client's token.
    spins = int(request.json["spins"])

    cur = get_db().cursor()
    # this was the minimum value when this table was generated
    # do 80% of this value to account for a client that has a stale copy of
    # the high score list (due to caching)
    # todo: could we just add an INC index on spins?
    minimum = int(cur.execute("SELECT min FROM minimum").fetchone()["min"] * 0.8)

    # TODO: race condition between MINIMUM and updating the high score list/database file
    if spins <= minimum:
        abort(401, "You aren't actually on the high score list, liar")

    if "name" in request.json:
        name = request.json["name"]
        if type(name) != str:
            abort(400, "Oops")
    else:
        # just use the first bit of the UUID instead
        name = request.json["id"].split("-")[0]

    if len(name) > 16 or len(name) < 2:
        # todo: sentiment analysis
        abort(400, "I hate your name buddy")

    id = str(request.json["id"])
    spins = int(request.json["spins"])
    timestamp = response.json["timestamp"]

    attempts = 0

    while attempts < 4:
        try:
            cur.execute(
                "REPLACE INTO highscores (id, name, spins, last_update) VALUES (?, ?, ?, ?)",
                (id, name, spins, timestamp),
            )
            break
        except sqlite3.IntegrityError as e:
            abort(401, "You're trying to be tricky, aren't you?")
        except sqlite3.Error as e:
            print(e)
            attempts += 1

    if attempts == 4:
        abort(500, "Oops")

    return response


def get_top_five():
    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = make_dicts
    cur = db.cursor()

    attempts = 0

    while attempts < 4:
        try:
            result = cur.execute(
                "SELECT id, name, spins FROM highscores ORDER BY spins DESC LIMIT 5;"
            ).fetchall()
            break
        except sqlite3.Error as e:
            print(e)
        attempts += 1

    db.close()

    return result


if app.debug:

    @app.route(f"/v{VERSION}/debugleaderboard", methods=["GET"])
    def debugleaderboard():
        return jsonify({"leaderboard": get_top_five()})


def write_leaderboard():
    # todo: we need to update the record instead of always inserting
    # and schedule cleanup task to run infrequently compared to the expected
    # time between intervals
    top_5 = get_top_five()
    with open(app.config["HIGHSCORE_FILE"], "w") as f:
        f.write(json.dumps({"leaderboard": top_5}))

    # update the lowest high score
    db = sqlite3.connect(app.config["DATABASE"])
    cur = db.cursor()
    cur.execute("BEGIN TRANSACTION;")

    lowest_highscore = int(top_5[-1]["spins"])

    try:
        cur.execute("DELETE FROM minimum;")
        cur.execute("INSERT INTO minimum (min) VALUES (?);", (lowest_highscore,))
        cur.execute("COMMIT;")
        db.commit()
    except sqlite3.DatabaseError as e:
        cur.execute("ROLLBACK;")
        print("UH OH")
        raise e
    finally:
        db.close()


if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    sched = BackgroundScheduler()
    sched.add_job(func=write_leaderboard, trigger="interval", minutes=1)
    sched.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: sched.shutdown())
