# TODO


## Client

1. ~~Detect if is PWA~~
2. ~~Persist what needs to be persisted if it is a PWA~~
3. Add UI for advertising the app
4. Tweak UI to allow retries on a server error
5. ~~Tell the server if we are an app or not~~
6. App on boarding (first run) message, outline differences
7. Allow for greater re-syncing if we exceed the three hours worth of spins between
   checkin test
8. ~~Use different endpoints if we're an app (v2?)~~
9. Get apple PWA icons working
10. Mute button
11. Fix safari leaderboard layout bug
12. Make modals look better
13. Clean up code / move between files
14. **Periodically update code**

## Server

1. ~~Include if is app in token, so a client can't change its mind~~
2. ~~Don't include IP in token if it is an app~~
3. ~~If is app, don't enforce 12 hour rule~~
4. ~~If is app, enforce 3 hours worth of spins rule~~
5. ~~Add seperate endpoints if is app, change behavior~~
6. ~~Add second database for app metadata~~
7. Change rate limiting to use id instead of ip address
8. 