"use strict";

const DATES_OF_INTEREST = [
    new Date(Date.UTC(2020, 9, 30, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 10, 6, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 10, 13, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 10, 20, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 10, 27, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 11, 4, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 11, 11, 7, 0, 0, 0)),
    new Date(Date.UTC(2020, 11, 18, 7, 0, 0, 0))
]

const SONGS = [
    new Audio("sound/babyyoda.mp3"),
    new Audio("sound/rap.mp3"),
    new Audio("sound/theme.mp3")
]

const LEADERBOARD_UPDATE_INTERVAL_MS = 1234;

const YODA = document.getElementById("yoda");
const COUNTER = document.getElementById("counter");
const MESSAGES = document.getElementById("messages");
const COUNTDOWN = document.getElementById("countdown");
const TARGET_DATE = getNextDoi();
const LEADERBOARD = document.getElementById("leaderboard");
const LEADERBOARD_TABLE = document.getElementById("leaderboard-table");

const LEADER_1 = document.getElementById("leader-1");
const LEADER_2 = document.getElementById("leader-2");
const LEADER_3 = document.getElementById("leader-3");
const LEADER_4 = document.getElementById("leader-4");
const LEADER_5 = document.getElementById("leader-5");
const LEADERS = [LEADER_1, LEADER_2, LEADER_3, LEADER_4, LEADER_5];

const LEADERBOARD_URL = "http://localhost:5000/v1/debugleaderboard"

let rotationAngle = 0;
let rotations = 0;
let lastPlayed = -1;
let leaderboardVisible = false;
let leaderboardButtonVisible = false;
let leaders = null;

// Values from the server
let lastTimestamp = null;
let lastToken = null;
let id = null;

function getRandomInt(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min) + min); //The maximum is exclusive and the minimum is inclusive
}

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

function rotateYoda() {
    YODA.style.transform = "translate(-50%, -50%) rotate(" + rotationAngle.toString() + "deg)";
    rotationAngle = (rotationAngle + 4 );

    if (rotationAngle % 360 != rotationAngle) {
        ++rotations;
        COUNTER.innerText = rotations.toString();
    }

    rotationAngle = rotationAngle % 360;
}

function updateClock() {
    let diff = DATES_OF_INTEREST[TARGET_DATE] - new Date();

    if (diff < 0) {
        clearInterval(clockInterval);
        // todo: play alert sound?
        COUNTDOWN.innerText = "00:00:00.00"
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
            row.cells[0].innerText = i + 1;
            row.cells[1].innerText = highscores[i]["name"];
            row.cells[2].innerText = highscores[i]["spins"];
        }

        // hide extra rows
        while (i < 5) {
            for (let j = 0; j < 3; ++j) {
                LEADERS[i].cells[j].innerText = "";
            }
            ++i;
        }
    })
}

LEADERBOARD.addEventListener("touch", toggleLeaderboard);
LEADERBOARD.addEventListener("click", toggleLeaderboard);

updateHighscores()
let highscoreInterval = setInterval(updateHighscores, LEADERBOARD_UPDATE_INTERVAL_MS);

if (TARGET_DATE != -1) {
    updateClock();
    COUNTDOWN.style.visibility = "visible";
    let clockInterval = setInterval(updateClock, 10);
}

let rotateInterval = setInterval(rotateYoda, 32)
initializeSongCallbacks()