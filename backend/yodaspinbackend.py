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
from flask_cors import CORS

from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
CORS(app)
VERSION = "1"

# Security related stuff
MAX_CONTENT_LENGTH = 300

try:
    import config.py
except ModuleNotFoundError as e:
    # default configuration
    NUMBER_OF_PROXIES = 2  # cloudflare, nginx, app
    SECRET = b"Burritos are my favorite animal"
    DATABASE = "backend/yoda.db"
    HIGHSCORE_FILE = "highscores.txt"

# The following constants must be kept in sync with the client
DEGREES_PER_INTERVAL = 4
SPIN_TIMER_INTERVAL_MS = 32
SPINS_BETWEEN_UPDATES = 31
MINIMUM_INITIAL_SPINS_FOR_REGISTRATION = SPINS_BETWEEN_UPDATES
MAXIMUM_INITIAL_SPINS_FOR_REGISTRATION = 2 * SPINS_BETWEEN_UPDATES

TIME_FOR_ONE_SPIN_MS = (360 / DEGREES_PER_INTERVAL) * 32
EXPECTED_TIME_BETWEEN_UPDATES_MS = SPINS_BETWEEN_UPDATES * TIME_FOR_ONE_SPIN_MS
EXPECTED_TIME_BETWEEN_UPDATES_S = EXPECTED_TIME_BETWEEN_UPDATES_MS / 1000


def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value)
                for idx, value in enumerate(row))

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
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

    if len(forward_chain) < NUMBER_OF_PROXIES:
        abort(403, "Nice try hackerman")

    # todo: configure nginx to only accept requests from cloudflare?
    user_ip = forward_chain[-1 * NUMBER_OF_PROXIES]
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

    return hmac.digest(SECRET, m, "MD5")


@app.route(f"/v{VERSION}/register", methods=["POST"])
def register():
    sanity_checks()

    # reject if there are more than 4 active connections from this IP address
    # (sorry people behind NAT)

    # we return to the client an HMAC of
    # (1) their IP
    # (2) a timestamp
    # (3) a uuid we generate
    # (4) the current number of spins (bounded)
    # The client then uses this has hash as a token when they go to do an update
    # The server saves no state until a request to update has been sent. The server
    # then validates the token, inserts a record in the DB, and the user is "registered"
    addr = get_ip_from_request()
    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    id = uuid.uuid4()
    body = request.json

    if "spins" not in body:
        abort(400, "Learn to code")
    spins = int(body["spins"])

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
        or "spins" not in body
        or "token" not in body
        or "timestamp" not in body
    ):
        abort(400, "Learn to code")

    id = uuid.UUID(str(body["id"]))
    spins_from_client = int(body["spins"])
    old_timestamp = int(body["timestamp"])

    if old_timestamp < 0:
        abort(422, "Nice try buddy")

    addr = get_ip_from_request()
    token = bytearray.fromhex(body["token"])
    calculated_token = get_secret_hash(
        old_timestamp,
        bytes(addr, "ascii"),
        id.bytes,
        spins_from_client - SPINS_BETWEEN_UPDATES,
    )

    if not hmac.compare_digest(calculated_token, token):
        abort(401, "You lied to me")

    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    # todo: if early, increment the new timestamp
    if abs(timestamp - EXPECTED_TIME_BETWEEN_UPDATES_S - old_timestamp) >= 1 and False:
        abort(403, "Timing incorrect :(")

    # at this point, the hash (and therfore the spin count) they gave is correct
    # and the timing is correct. issue a new token
    new_token = get_secret_hash(
        timestamp, bytes(addr, "ascii"), id.bytes, spins_from_client
    )

    return jsonify(
        {
            "timestamp": timestamp,
            "token": new_token.hex(),
        }
    )


@app.route(f"/v{VERSION}/updateleaderboard", methods=["POST"])
def updateleaderboard():
    response = update()

    # we are going to hold the response hostage. if they actually don't deserve
    # to be on the leaderboard, we reject them and don't issue a token to prevent
    # people from abusing this endpoint

    # at this point, we have authenticated the client's token.
    spins = int(request.json["spins"])

    cur = get_db().cursor()
    # this was the minimum value when this table was generated
    # do 80% of this value to account for a client that has a stale copy of
    # the high score list (due to caching)
    # todo: could we just add an INC index on spins?
    minimum = int(cur.execute("SELECT min FROM minimum").fetchone()[0] * 0.8)

    # todo: race condition between MINIMUM and updating the high score list/database file
    if spins <= minimum:
        abort(401, "You aren't actually on the high score list, liar")

    if "name" in request.json:
        name = request.json["name"]
        if len(name) > 10:
            # todo: sentiment analysis
            abort(400, "Too much long")
    else:
        name = request.json["id"].split("-")[0]
    id = str(request.json["id"])
    spins = int(request.json["spins"])
    timestamp = response.json["timestamp"]

    try:
        cur.execute(
            "INSERT INTO highscores (id, name, spins, last_update) VALUES (?, ?, ?, ?)",
            (id, name, spins, timestamp),
        )
    except sqlite3.IntegrityError as e:
        abort(401, "You're trying to be tricky, aren't you?")

    return response

def get_top_five():
    db = sqlite3.connect(DATABASE)
    db.row_factory = make_dicts
    cur = db.cursor()
    result = cur.execute("SELECT id, name, spins FROM highscores ORDER BY spins DESC LIMIT 5;").fetchall()
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
    with open(HIGHSCORE_FILE, 'w') as f:
        f.write(json.dumps({"leaderboard":top_5}))
    
    # update the lowest high score
    db = sqlite3.connect(DATABASE)
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
    

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    sched = BackgroundScheduler()
    sched.add_job(
        func=write_leaderboard, 
        trigger="interval",
        minutes=1
    )
    sched.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: sched.shutdown())
 