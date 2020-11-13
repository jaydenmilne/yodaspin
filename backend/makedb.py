import sys
import sqlite3

db_path = sys.argv[1]
print(f"Making db at {db_path}")
db = sqlite3.connect(db_path)
cur = db.cursor()

cur.executescript("""
CREATE TABLE "highscores" (
	"id"	TEXT NOT NULL CHECK(length("id") == 36) UNIQUE,
	"name"	TEXT NOT NULL CHECK(length("name") <= 20 AND length("name") >= 2),
	"spins"	INTEGER NOT NULL,
	"last_update"	INTEGER NOT NULL,
	PRIMARY KEY("id")
);
CREATE TABLE "minimum" (
	"min"	INTEGER NOT NULL
);
CREATE INDEX "spinsdex" ON "highscores" (
	"spins"	DESC
);
""")
cur.close()
db.commit()
