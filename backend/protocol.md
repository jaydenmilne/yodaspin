# How the Backend and the Client Communicate

There are 3 main goals:

1. A client should not be allowed to cheat (go faster than the should)
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

## Differences between the web site and PWA app protocol
The web site and the PWA have slight differences in the protocol, given the different
challenges each pose. The web site is all about keeping one tab around and seeing
how long you can go without closing it, while the app is more about how much time
you can dedicate your phone to running it.

### Checkin Time Limits
For the web site, we enforce a 12 hour maximum time between checkins (and this
really should probably be tighter), while for the app, instead we limit users from
increasing their spins by more than what you could do in a few hours.

The goal of this is to allow app users to go a while between checkins, but preventing
them from cheating and jumping ahead a significant amount without running the app.

### IP Addresses
We also don't enforce having the same IP address between checkins on the PWA, for
obvious reasons.

### Scoreboards
Because of these differences, we have different databases for the app and the web
site, since the 'challenge' is different.


## Edge cases and how I am attempting to mitigate them

### Server goes down
Unless the server gives an error code, the frontend won't indicate that anything
is amiss if the backend goes completely AWOL. The backend will allow updates
with a maximum of 12 hours between the last checkin before it rejects them, so if
a client lost connectivity for whatever reason, as long as I fix it or they reconnect
within 12 hours everything proceeds smoothly

### Client lying about previous checkin (number of spins, timestamp, id)
This is what the `token` is for - an hmac of the data we need back from the client
since we don't keep state, so that they store it for us and we can authenticate
it after they give it back to us.

### Fast-forward attack
Someone opens the console and sets `rotations` to `1,000,000`.

We try and prevent this by calculating how many spins we expect the client to have
done since the last checkin, and rejecting the update if it is more than they 
should've been able to.

### Client-server desync
Because of the above mitigation, I've seen clients get out of sync by as much as
5 spins before somehow. To prevent that from ending your run, if the client went
too fast by about 13 spins, the server will return what it thinks the client should
be at, and the client will not count the next (clientSpins - serverSpins) spins,
so that they re-synchronize

### Token/Secret sharing

Someone gets a decently high score, and then shares their token/id with others.

While this is difficult to prevent, they will only be able to have one spot on
the high score board since it is indexed by the id. If someone shares their secrets,
the most that could happen is that they fight over a high score spot **and** they
can keep that high score going indefinitely. If I notice the name bouncing around
a lot, I'd just ban the ID somehow.
