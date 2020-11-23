"use strict";

const DATES_OF_INTEREST = [
    new Date(Date.UTC(2020, 9, 30, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 10, 6, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 10, 13, 8, 1, 0, 0)),
    new Date(Date.UTC(2020, 10, 20, 8, 1, 0, 0)),
    new Date(Date.UTC(2020, 10, 27, 8, 1, 0, 0)),
    new Date(Date.UTC(2020, 11, 4, 8, 1, 0, 0)),
    new Date(Date.UTC(2020, 11, 11, 8, 1, 0, 0)),
    new Date(Date.UTC(2020, 11, 18, 8, 1, 0, 0))
]

const SONGS = [
    new Audio("sound/babyyoda.mp3"),
    new Audio("sound/rap.mp3"),
    new Audio("sound/theme.mp3")
]

const LEADERBOARD_UPDATE_INTERVAL_MS = 10000;

const YODA = document.getElementById("yoda");
const COUNTER = document.getElementById("counter");
const MESSAGES = document.getElementById("messages");
const COUNTDOWN = document.getElementById("countdown");
const TARGET_DATE = getNextDoi();
const LEADERBOARD = document.getElementById("leaderboard");
const LEADERBOARD_TABLE = document.getElementById("leaderboard-table");
const OVERLAY_DIV = document.getElementById("overlay-div");
const MODAL_TITLE = document.getElementById("modal-title");
const MODAL_MESSAGE = document.getElementById("modal-message");
const MODAL_INPUT = document.getElementById("modal-input");
const MODAL_BUTTON = document.getElementById("modal-btn");
const LEADER_1 = document.getElementById("leader-1");
const LEADER_2 = document.getElementById("leader-2");
const LEADER_3 = document.getElementById("leader-3");
const LEADER_4 = document.getElementById("leader-4");
const LEADER_5 = document.getElementById("leader-5");
const LEADERS = [LEADER_1, LEADER_2, LEADER_3, LEADER_4, LEADER_5];
const HIGHSCORE_STAR_MOVEMENT_SPEED = 0.22;

let LEADERBOARD_URL = null;
let API_URL = null;
let REGISTER_ENDPOINT = null;
let UPDATE_ENDPOINT = null;
let UPDATELEADERBOARD_ENDPOINT = null;

function isApp() {
    return displayMode == "web";
}


/**
 * Class that will persist to localstorage, or session storage if not app
 */
class StateStorage {
    constructor(isApp) {
        this.isApp = isApp;
        this.storage = this.isApp ? window.localStorage : window.sessionStorage;
    }

    set(key, val) {       
        this.storage.setItem(key, JSON.stringify(val))
    }

    inc(key, delta) {
        this.set(key, this.get(key) + delta);
    }

    get(key) {
        return JSON.parse(this.storage.getItem(key));
    }

    has(key) {
        return this.storage.getItem(key) != null;
    }
}



let rotationAngle = 0;
let lastPlayed = -1;
let leaderboardVisible = false;
let leaderboardButtonVisible = false;
let leaders = null;
let modalMode = null;
let starMovementSpeed = 0.1;
let minHighScore = Infinity;

let displayMode = "web";
let state = null;


// Constants must be kept in sync with the server!
const SPINS_BETWEEN_UPDATES = 13;
const YODA_TIME_FOR_1_REVOLUTION_MS = 2880;  // this just looks right, you know?

function getRandomInt(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min) + min); //The maximum is exclusive and the minimum is inclusive
}

let initialOffset = getRandomInt(0, SPINS_BETWEEN_UPDATES);
let registerAt = initialOffset;
let registered = false;


function storeDefaults() {
    // Store the defaults in localStorage
    state.set("rotations", 0);
    state.set("name", null);
    state.set("hadHighscore", false);
    state.set("skipUpdate", false);
    state.set("spinsToSkip", -1);
    state.set("lastTimestamp", null);
    state.set("token", null);
    state.set("id", null);
    state.set("lastSpins", -1);
    state.set("faulted", false);
    state.set("init", true);
}


window.addEventListener("DOMContentLoaded", () => {
    if (navigator.standalone) {
      displayMode = "standalone-ios";
    }
    if (window.matchMedia("(display-mode: standalone)").matches) {
      displayMode = "standalone";
    }
    state = new StateStorage(displayMode != "web");
    if (displayMode != "web") {
        // check if we've run before
        if (!state.has("init")) {
            storeDefaults();
        } else {
            // we've run
            registered = true;
            registerAt = 1;
            COUNTER.innerText = state.get("rotations").toLocaleString();
            if (state.get("hadHighscore")) {
                starMovementSpeed = HIGHSCORE_STAR_MOVEMENT_SPEED;
                COUNTER.style.color = "gold";
            }
        }
    } else {
        storeDefaults();
    }

    if (location.hostname === "localhost" || location.hostname === "127.0.0.1" || location.hostname === "") {
        LEADERBOARD_URL = "http://localhost:5000/debugleaderboard/";
        API_URL = "http://localhost:5000/";
    } else {
        LEADERBOARD_URL = "https://leaders.yodaspin.com/";
        API_URL = "https://api.yodaspin.com/";
    }

    if (displayMode == "web") {
        LEADERBOARD_URL += "v1";
        API_URL += "v1";
    } else {
        LEADERBOARD_URL += "v2";
        API_URL += "v2";
    }

    REGISTER_ENDPOINT = `${API_URL}/register`;
    UPDATE_ENDPOINT = `${API_URL}/update`;
    UPDATELEADERBOARD_ENDPOINT = `${API_URL}/updateleaderboard`;

    requestAnimationFrame(rotateYoda);

    LEADERBOARD.addEventListener("touch", toggleLeaderboard);
    LEADERBOARD.addEventListener("click", toggleLeaderboard);

    // When they press enter in the textarea, submit the form
    MODAL_INPUT.addEventListener("keyup", function(event) {
        if (event.keyCode === 13) {
        event.preventDefault();
        MODAL_BUTTON.click();
        }
    });

    updateHighscores()
    var highscoreInterval = setInterval(updateHighscores, LEADERBOARD_UPDATE_INTERVAL_MS);
    var clockInterval = 0;

    if (TARGET_DATE != -1) {
        updateClock();
        COUNTDOWN.style.visibility = "visible";
        clockInterval = setInterval(updateClock, 10);
    }

    initializeSongCallbacks()

    window.onbeforeunload = function() { 
        return "Baby Yoda will be SAD if you leave, are you sure??";
    }


});

console.log(`I will register at ${registerAt}`);

// only the finest code copy pasted from Stack Overflow
function lpad(str) {
    while (str.length < 2)
        str = '0' + str;
    return str;
}

function initializeSongCallbacks() {
    SONGS.forEach( (song) => {
        song.addEventListener("ended", () => {
            setTimeout(playRandomSong, getRandomInt(1000, 15000));
        });
    });
}

function playRandomSong() {
    let song = getRandomInt(0, SONGS.length);
    while (song == lastPlayed) {
        song = getRandomInt(0, SONGS.length);
    }
    lastPlayed = song;
    SONGS[song].play();

    console.debug(`playing song ${song}`)

}

function getNextDoi() {
    let now = new Date();
    let i = 0;

    while (i < DATES_OF_INTEREST.length) {
        if (DATES_OF_INTEREST[i] > now) {
            return i;
        }
        ++i;
    }
    return -1;
}

async function initialRegistration() {
    state.set("lastSpins", state.get("rotations"));
    const response = await fetch(REGISTER_ENDPOINT, {
        "method": "POST",
        "body": JSON.stringify({
            "spins": state.get("rotations")
        }),
        "headers": new Headers({
            "Content-Type": "application/json"
        })
    })

    if (!response.ok) {
        console.error(`Failed to register! ${response.status}: ${response.text}`);
        return;
    }

    let body = await response.json();
    // save response data
    registered = true;
    state.set("lastTimestamp", body["timestamp"]);
    state.set("token", body["token"]);
    state.set("id", body["id"]);
    state.set("name", body["id"].split("-")[0]);

    console.log(`Registered, id='${body["id"]}'`);
}

function hasHighScore() {
    return state.get("rotations") > minHighScore && !state.get("faulted");
}

function getUpdateEndpoint() {
    return (hasHighScore()) ? UPDATELEADERBOARD_ENDPOINT : UPDATE_ENDPOINT;
}

async function refreshToken() {
    if (state.get("faulted") || state.get("skipUpdate")) return;

    let endpoint = getUpdateEndpoint();
    // TODO: Retry logic
    const response = await fetch(endpoint, {
        "method": "POST",
        "body": JSON.stringify({
            "token": state.get("token"),
            "previous-spins": state.get("lastSpins"),
            "spins": state.get("rotations"),
            "timestamp": state.get("lastTimestamp"),
            "id": state.get("id"),
            "name": state.get("name"),
        }),
        "headers": new Headers({
            "Content-Type": "application/json"
        })
    })

    if (!response.ok) {
        if (response.status == 403) {
            // uh oh
            state.set("faulted", true);
            let error = await response.json();

            displayModal("Lost Server Connection", `You've lost your connection with the server (reason ${error["error"]} / ${response.status}). This can happen because your device went to sleep, lost connectivity, or the tab was in the background. You will not get on the leaderboard.`, "Darn.");
        } else if (response.status < 500 && response.status >= 400 && response.status != 403) {
            state.set("faulted", true);
            let error = await response.json();

            displayModal("Something went wrong!", `Something broke (${JSON.stringify(error)} / ${response.status}), and your high score will not update now, this is a bug. Sorry. \n Screenshot this and send it to Jayden`, "Learn to code dude");
        }
        // If it isn't a 400 error, then we don't do anything drastic. The server
        // could just be down temporarily. As long as it comes back up within
        // 12 hours we can get a new token and pretend this never happened
        console.error(`Surpressing backend error ${response.status}`);
        return;
    }
    
    state.set("lastSpins", state.get("rotations"));
    let body = await response.json();

    if (body["spins"] < state.get("lastSpins")) {
        // We went too fast and the server is correcting us. 
        console.log("Cooling our jets...");
        state.set("spinsToSkip", state.get("lastSpins") - body["spins"]);
        state.set("lastSpins", body["spins"]);
        state.set("skipUpdate", true);  // Prevent a second update from being triggered
    }

    state.set("lastTimestamp", body["timestamp"]);
    state.set("token", body["token"]);

    console.log(`Updated token, new='${state.get("token")}', lastTimestamp='${state.get("lastTimestamp")}', spins='${state.get("lastSpins")}'`);
}


function onSpinComplete() {
    
    // To resynchronize with the server when we get ahead
    if (state.get("spinsToSkip") > 0) {
        state.inc("spinsToSkip", -1);
    } else {
        state.inc("rotations", 1);
        state.inc("spinsToSkip", -1);
    }

    if (state.get("spinsToSkip") == -1) {
        state.set("skipUpdate", false);
    }

    COUNTER.innerText = state.get("rotations").toLocaleString();
    document.title = `${ hasHighScore() ? "🤩 " : ""}YODA SPIN | ${state.get("rotations").toLocaleString()}`;


    if (state.get("rotations") < SPINS_BETWEEN_UPDATES) {
        if (!registered && state.get("rotations") >= registerAt) {
            initialRegistration();
        }
        return;
    }
    
    // check to see if we are on the leaderboard
    if (hasHighScore() && !state.get("hadHighscore")) {
        namePromptModal();
        state.set("hadHighscore", true);
        COUNTER.style.color = "gold";
        starMovementSpeed = HIGHSCORE_STAR_MOVEMENT_SPEED;
    }

    if ((state.get("rotations") - registerAt) % SPINS_BETWEEN_UPDATES == 0) {
        // time to get a new token!
        refreshToken();
    }
}

let last = 0;
function rotateYoda(clock) {
    // calculate the degrees to rotate
    let delta = clock - last;
    last = clock;
    let angleDelta = (delta / YODA_TIME_FOR_1_REVOLUTION_MS) * 360;
    rotationAngle += angleDelta;
    YODA.style.transform = `translate(-50%, -50%) rotate(${rotationAngle}deg)`;

    if (rotationAngle >= 360) {
        onSpinComplete();
        rotationAngle = rotationAngle % 360;
    }

    requestAnimationFrame(rotateYoda);
}

function updateClock() {
    let diff = DATES_OF_INTEREST[TARGET_DATE] - new Date();

    if (diff < 0) {
        clearInterval(clockInterval);
        // todo: play alert sound?
        COUNTDOWN.innerText = "00:00:00:00.00"
        return;
    }

    let days = diff / (1000*60*60*24);
    let hours = (days - Math.floor(days)) * 24;
    let minutes = (hours - Math.floor(hours)) * 60;
    let seconds = (minutes - Math.floor(minutes)) * 60;
    let thousands = Math.floor((seconds - Math.floor(seconds)) * 100)

    COUNTDOWN.innerText = `${lpad(Math.floor(days).toString())}:${lpad(Math.floor(hours).toString())}:${lpad(Math.floor(minutes).toString())}:${lpad(Math.floor(seconds).toString())}.${lpad(Math.floor(thousands).toString())}`
}

// Wait until user interacts to play anything
document.body.addEventListener("click", () => {
    if (lastPlayed == -1) {
        playRandomSong();
    }
});

document.body.addEventListener("touch", () => {
    if (lastPlayed == -1) {
        playRandomSong();
    }
});

function toggleLeaderboard() {
    leaderboardVisible = !leaderboardVisible;

    if (leaderboardVisible) {
        LEADERBOARD.style.opacity = "100%";
        LEADERBOARD_TABLE.style.visibility = "visible";
    } else {
        LEADERBOARD.style.opacity = "30%";
        LEADERBOARD_TABLE.style.visibility = "collapse";
    }

}

function updateHighscores() {
    fetch(LEADERBOARD_URL, {mode: 'cors'}).then(
        response => {
            if (response.status != 200) {
                console.error("Failed to hit highscore backend!")
                console.error(response)
            }
            return response.json();
        }
    ).then( response => {
        let leaders = response["leaderboard"];
        let highscores = response["leaderboard"];

        if (!leaderboardButtonVisible) {
            LEADERBOARD.style.visibility = "visible";
        }

        let i = 0;
        for ( ; i < highscores.length; ++i) {
            let row = LEADERS[i];
            if (highscores[i]["name"] == state.get("name")) {
                highscores[i]["name"] = `🎉 ${highscores[i]["name"]} 🎉`;
                row.cells[0].style.color = "gold";
                row.cells[1].style.color = "gold";
                row.cells[2].style.color = "gold";
            } else {
                row.cells[0].style.color = "inherit";
                row.cells[1].style.color = "inherit";
                row.cells[2].style.color = "inherit";
            }
            row.cells[0].innerText = i + 1;
            row.cells[1].innerText = highscores[i]["name"];
            row.cells[2].innerText = highscores[i]["spins"].toLocaleString();
        }

        // update the minimum high score (for detecting if we are on the leaderboard)
        minHighScore = highscores[highscores.length - 1]["spins"]

        // hide extra rows
        while (i < 5) {
            for (let j = 0; j < 3; ++j) {
                LEADERS[i].cells[j].innerText = "";
            }
            ++i;
        }
    })
}

function modalButtonPress(e) {

    if (modalMode == "input") {
        // todo: handle input here
        // validate input
        let input = MODAL_INPUT.value;
        if (input.length < 2 || input.length > 16) {
            MODAL_MESSAGE.innerText = "Between 2 and 16 chars buddy";
            return;
        }
        state.set("name", input);
    }

    OVERLAY_DIV.style.visibility = "hidden";

}

MODAL_BUTTON.addEventListener("click", (e) => {
    modalButtonPress(e)
});

/**
 * Displays the modal, without an input, and dismisses it when the user presses OK
 * @param {String} title 
 * @param {String} message 
 */
function displayModal(title, message, btn_text) {
    MODAL_TITLE.innerText = title;
    MODAL_MESSAGE.innerText = message;
    MODAL_INPUT.style.visibility = "hidden";
    MODAL_BUTTON.innerText = btn_text;
    // unhide the display modal
    OVERLAY_DIV.style.visibility = "visible";
    modalMode = "message";
}

function namePromptModal() {
    displayModal("GOOD NEWS", "You're on the leaderboard! Put in a name. \nThe leaderboard takes a while to update.", "LET'S GOOO");
    MODAL_INPUT.style.visibility = "inherit";
    modalMode = "input";
}



// PWA Stuff
navigator.serviceWorker.register("./serviceworker.js");


