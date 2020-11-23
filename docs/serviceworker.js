"use strict";

const cacheName = "yodaspin_v1";

function onInstall(event) {
    event.waitUntil(
        caches.open(cacheName).then((cache) => {
            return cache.addAll([
                "serviceworker.js",
                "sound/babyyoda.mp3",
                "sound/index.html",
                "sound/rap.mp3",
                "sound/theme.mp3",
                "index.html",
                "spin.js",
                "stars.js",
                "yoda.css",
                "yoda.jpg",
                "favicon.ico"
            ])
        }));
}

// todo: periodic update
async function onFetch(event) {
    event.respondWith(
        fetch(event.request).then(async (response) => {
            // update what is in the cache, in case we go offline next
            let cache = await caches.open(cacheName);
            if (event.request.method == "GET") {
                cache.put(event.request, response.clone());
            }
            return response;
        }).catch( (err) => {
            caches.match(event.request).then((response) => {
                return response;
            })}

    ));
    // Try fetching it directly first, if that fails,
    // use what we've cached


/*
    caches.match(event.request).then((response) => {
        return response || fetch(event.request);
    });
*/
}

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
            if(key !== cacheName) {
                return caches.delete(key);
            }
            }));
        })
    );
});


self.addEventListener("fetch", onFetch);
self.addEventListener("install", onInstall);
