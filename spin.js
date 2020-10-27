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
    new Audio("sound/babyyoda.webm"),
    new Audio("sound/rap.webm"),
    new Audio("sound/theme.webm")
]

const YODA = document.getElementById("yoda");
const COUNTER = document.getElementById("counter");
const MESSAGES = document.getElementById("messages");
const COUNTDOWN = document.getElementById("countdown");
const TARGET_DATE = getNextDoi();

let rotationAngle = 0;
let rotations = 0;
let lastPlayed = -1;

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

function playRandomSong() {
    let song = getRandomInt(0, SONGS.length);
    while (song == lastPlayed) {
        song = getRandomInt(0, SONGS.length);
    }
    lastPlayed = song;
    SONGS[song].play();
    console.debug(`playing song ${song}`)

    SONGS[song].addEventListener("ended", () => {
        setTimeout(playRandomSong, getRandomInt(1000, 10000));
    })
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

if (TARGET_DATE != -1) {
    updateClock();
    COUNTDOWN.style.visibility = "visible";
    let clockInterval = setInterval(updateClock, 10);
}

let rotateInterval = setInterval(rotateYoda, 32)