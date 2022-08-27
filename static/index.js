"use strict";
import { KeyEvent } from "./keys.js";
const apiUrl = window.location.origin + "/api/v1";
function main(e){
    
}
function keyboardEventLogger(e){
    function getKeyByValue(object, value) {
        return Object.keys(object).find(key => object[key] === value);
    }
    const event_json = {code: e.code, keyName: getKeyByValue(KeyEvent, e.keyCode)};
    fetch(apiUrl+"/log", {
        method: "POST",
        body: JSON.stringify(event_json)
    });
}

// Object.keys(window).forEach(key => {
//     if (/^on/.test(key)) {
//         window.addEventListener(key.slice(2), event => {
//             const event_json = Object.assign({}, event, {"type": key});
//             fetch(apiUrl+"/log", {
//                 method: "POST",
//                 body: JSON.stringify(event_json)
//             });
//         });
//     }
// });

document.addEventListener("keydown", keyboardEventLogger);
// document.addEventListener("keyup", keyboardEventLogger);
// document.addEventListener("keypress", keyboardEventLogger);
document.addEventListener("DOMContentLoaded", main);