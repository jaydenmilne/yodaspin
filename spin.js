"use strict";

const YODA = document.getElementById("yoda");
let ROTATION = 0;

let interval = setInterval(rotateYoda, 16)

function rotateYoda() {
    YODA.style.transform = "translate(-50%, -50%) rotate(" + ROTATION.toString() + "deg)";
    ROTATION = (ROTATION + 2 ) % 360;
}
