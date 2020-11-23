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
from flask_limiter import Limiter
from flask_cors import CORS

from apscheduler.schedulers.background import BackgroundScheduler


def get_ip_from_request():
    """
    Returns the IP address of the current request
    """
    if app.debug:
        return request.remote_addr

    forward_chain = request.headers.getlist("X-Forwarded-For")

    if len(forward_chain) < app.config["NUMBER_OF_PROXIES"]:
        abort(403, "Nice try hackerman")

    # todo: configure nginx to only accept requests from cloudflare?
    user_ip = forward_chain[-1 * app.config["NUMBER_OF_PROXIES"]]
    return user_ip


app = Flask(__name__)
limiter = Limiter(app, key_func=get_ip_from_request)

app.config.from_envvar("YODASPIN_SETTINGS")

if app.debug:
    CORS(app)
else:
    CORS(app, resources={"/v1/*": {"origins": app.config["CORS_DOMAIN"]}})

VERSION = 1

# Security related stuff
MAX_CONTENT_LENGTH = 300

# The following constants must be kept in sync with the client
DEGREES_PER_INTERVAL = 4
SPIN_TIMER_INTERVAL_MS = 32
SPINS_BETWEEN_UPDATES = 13
MINIMUM_INITIAL_SPINS_FOR_REGISTRATION = 0
MAXIMUM_INITIAL_SPINS_FOR_REGISTRATION = SPINS_BETWEEN_UPDATES + 1


TIME_FOR_ONE_SPIN_MS = (360 / DEGREES_PER_INTERVAL) * 32
EXPECTED_TIME_BETWEEN_UPDATES_MS = SPINS_BETWEEN_UPDATES * TIME_FOR_ONE_SPIN_MS
EXPECTED_TIME_BETWEEN_UPDATES_S = EXPECTED_TIME_BETWEEN_UPDATES_MS / 1000

# Only allow 3 hours worth of spins between checkins, with the app
MAXIMUM_SPINS_BETWEEN_CHECKINS_APP = (3600 * 3 * 3000 ) // TIME_FOR_ONE_SPIN_MS

# this is used mostly to prevent people from spamming this endpoint quickly
MINIMUM_TIME_BETWEEN_UPDATES_S = EXPECTED_TIME_BETWEEN_UPDATES_S * 0.5
MAXIMUM_TIME_BETWEEN_UPDATES_S = 12 * 60 * 60  # 12 hours

APP_REPLACEMENT_IP_STRING = "application!!1"

def make_dicts(cursor, row):
    """
    Helper method to make parsing results from the database easier. Returns a dict
    of column:value.
    """
    return dict((cursor.description[idx][0], value) for idx, value in enumerate(row))

def get_db_path(version):
    if version == 1:
        return app.config["DATABASE"]
    elif version == 2:
        return app.config["APP_DATABASE"]
    else:
        abort(400, "Cant do the thin :(")

def get_db(version):
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(get_db_path(version))
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
def handle_error(e):
    return jsonify(error=str(e)), e.code


@app.route("/", methods=["GET"])
def status():
    """
    Quick status check to make sure the backend is running.
    """
    return "itsworkinganakin.gif"


def sanity_checks(version):
    """
    Try and weed out malicious or malformed input
    """
    if request.content_length > MAX_CONTENT_LENGTH:
        abort(413, description="Too much for me buddy")

    if not request.is_json:
        abort(400, "Bro can you even")
    
    if version not in [1, 2]:
        abort(400, "IDK homebro")


def get_secret_hash(timestamp, addr, client_id, spins):
    """
    timestamp: float
    addr: string
    client_id: uuid
    spins: int
    """
    m = bytearray()
    m.extend(bytes(str(timestamp), "ascii"))
    m.extend(spins.to_bytes(16, sys.byteorder))
    m.extend(bytes(addr, "ascii"))
    m.extend(client_id.bytes)

    return hmac.digest(app.config["SECRET"], m, "MD5")


def get_utc_timestamp():
    now = datetime.datetime.now()
    utc = now.replace(tzinfo=datetime.timezone.utc)
    return utc.timestamp()


@app.route(f"/v<int:version>/register", methods=["POST"])
#@limiter.limit("1/second")
def register(version):
    sanity_checks(version)
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
    if version == 1:
        addr = get_ip_from_request()
    else:
        addr = APP_REPLACEMENT_IP_STRING
    
    timestamp = get_utc_timestamp()
    client_id = uuid.uuid4()

    if (
        spins < MINIMUM_INITIAL_SPINS_FOR_REGISTRATION
        or spins > MAXIMUM_INITIAL_SPINS_FOR_REGISTRATION
    ):
        abort(401, "Trying to pull a fast one?")

    token = get_secret_hash(timestamp, addr, client_id, spins)

    return jsonify({"timestamp": str(timestamp), "id": client_id, "token": token.hex()})


@app.route(f"/v<int:version>/update", methods=["POST"])
def update(version):
    # sanity checks
    sanity_checks(version)
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
    client_id = body["id"]
    token = body["token"]

    if (
        type(previous_spins) != int
        or type(old_timestamp)
        not in [str, int]  # allow ints for old clients, todo: remove this
        or type(spins) != int
        or type(token) != str
        or type(client_id) != str
    ):
        abort(400, "That doesn't go there")

    try:
        old_timestamp = float(old_timestamp)
    except ValueError as e:
        abort(400, "That was an interesting timestamp")

    client_id = uuid.UUID(client_id)
    token = bytearray.fromhex(token)

    if version == 1:
        addr = get_ip_from_request()
    elif version == 2:
        addr = APP_REPLACEMENT_IP_STRING

    calculated_token = get_secret_hash(
        old_timestamp,
        addr,
        client_id,
        previous_spins,
    )

    if not hmac.compare_digest(calculated_token, token):
        abort(401, "You lied to me")

    timestamp = get_utc_timestamp()

    # the soonest they are allowed to check in again
    earliest_checkin = old_timestamp + MINIMUM_TIME_BETWEEN_UPDATES_S

    # the latest after their last token was issued they can check in again
    latest_checkin = old_timestamp + MAXIMUM_TIME_BETWEEN_UPDATES_S

    # this is meant to be just a slap on the wrist, really there is nothing
    # stopping a client from hammering this endpoint.
    # TODO: ban id if they check in too early somehow
    if timestamp < earliest_checkin:
        abort(403, f"Too soon")

    if timestamp > latest_checkin and version == 1:
        abort(403, f"Too late")

    # calculate what we would expect them to be at by based off of the time delta
    delta = timestamp - old_timestamp

    expected_spins = round(previous_spins + delta / (TIME_FOR_ONE_SPIN_MS / 1000))

    if expected_spins < spins:
        # they went too fast. set an override
        if abs(spins - expected_spins) < SPINS_BETWEEN_UPDATES:
            # in this situation, let them continue, this could be an innocent desync.
            # We return in this request the number of spins the client will detect
            # the discrepancy and adjust itself accordingly
            # I have seen desync in the wild up to 5 spins
            spins = expected_spins
        else:
            # they really went too fast, punish them
            abort(403, f"Cool your jets {expected_spins} / {spins}")

    if version == 2 and spins - previous_spins > MAXIMUM_SPINS_BETWEEN_CHECKINS_APP:
        spins = previous_spins + MAXIMUM_SPINS_BETWEEN_CHECKINS_APP

    # we allow them to go slower than expected, as long as they are in the
    # MAXIMUM_TIME_BETWEEN_UPDATES_S window

    # at this point, we have verified the integrity of the information they provided
    # and made sure that the amount of spins they gave is legal
    new_token = get_secret_hash(timestamp, addr, client_id, spins)

    return jsonify(
        {"timestamp": str(timestamp), "token": new_token.hex(), "spins": spins}
    )


@app.route(f"/v<int:version>/updateleaderboard", methods=["POST"])
#@limiter.limit("15/minute")
def updateleaderboard(version):
    response = update(version)

    # at this point, we have authenticated the client's token.
    spins = int(request.json["spins"])

    cur = get_db(version).cursor()
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


def get_top_five(version):
    db = sqlite3.connect(get_db_path(version))
    db.row_factory = make_dicts
    cur = db.cursor()

    attempts = 0

    while attempts < 4:
        try:
            result = cur.execute(
                "SELECT name, spins FROM highscores ORDER BY spins DESC LIMIT 5;"
            ).fetchall()
            break
        except sqlite3.Error as e:
            print(e)
        attempts += 1

    db.close()

    return result


if app.debug:

    @app.route(f"/debugleaderboard/v<int:version>", methods=["GET"])
    def debugleaderboard(version):
        return jsonify({"leaderboard": get_top_five(version)})


def write_leaderboard():
    # todo: we need to update the record instead of always inserting
    # and schedule cleanup task to run infrequently compared to the expected
    # time between intervals

    for highscorefile, version in [(app.config["HIGHSCORE_FILE"], 1), (app.config["APP_HIGHSCORE_FILE"], 2)]:
        top_5 = get_top_five(version)
        with open(highscorefile, "w") as f:
            f.write(json.dumps({"leaderboard": top_5}))

        # update the lowest high score
        db = sqlite3.connect(get_db_path(version))
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
    sched.add_job(func=write_leaderboard, trigger="interval", seconds=10)
    sched.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: sched.shutdown())
