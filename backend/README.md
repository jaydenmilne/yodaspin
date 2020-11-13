# How the Backend and the Client Communicate

There are 3 main goals:

1. A client should not be allowed to cheat
2. Minimize hits on the database (sqlite)
3. Avoid hitting a dynamic endpoint if at all possible

## Protocol

### Registration
The client starts by registering at `/v1/register`, sending the number of spins
it is at. This is so that clients can update at different intervals, ie starting
at 14 spins and then every 13 spins, so that all the high scores aren't multiples
of each other.

The server returns a `token`, `id`, the `timestamp` when it recieved the request, and
importantly, does not save any state. The token is an HMAC of the spins, id, ip address, and timestamp.

### Updating
The client periodically updates this token (it should be every `SPINS_BETWEEN_UPDATES`)
by sending the new amount of spins, and the information the server would
need to recreate and validate the `token` (`token`, `id`, `timestamp`, `previous-spins`).

The server first authenicates `id`, `timestamp`, and `previous-spins` by recreating
the HMAC and making sure it matches. After those values are authenticated, it computes
what the maximum number of spins should be, and makes sure the new value of `spins`
the client has sent does not exceed that. It also makes sure that too much time hasn't
passed. If all the checks pass, it issues a new token.

### Updating High Score
If the client decides it has a high score, it will begin hitting the `v1/updateleaderboard`
endpoint, which does the same as the `v1/update` endpoint except it will store
an entry in the database, if it exceeds the lowest of the top 5 scores.

## High Scores
Instead of having a highscore endpoint, every 10s the server calculates the top
5 and writes it to a file, which nginx serves statically from a different domain,
to allow more aggressive caching or sharding. Since every client polls for the 
high score list, this is so that there are no db accesses required.
