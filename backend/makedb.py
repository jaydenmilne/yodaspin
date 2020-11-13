import sys
import sqlite3

db_path = sys.argv[1]
print(f"Making db at {db_path}")
db = sqlite3.connect(db_path)
cur = db.cursor()

cur.executescript(
    """
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
"""
)

# things don't handle having no top score well
cur.executescript(
    """
INSERT INTO highscores (id, name, spins, last_update) VALUES ("474aff56-761d-40bb-959e-fc87630dfdc0", "roguenerd", 1, 1);
INSERT INTO minimum (min) VALUES (1);
"""
)

cur.close()
db.commit()
