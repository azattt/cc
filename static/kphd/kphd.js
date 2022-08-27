(function () {
    "use strict";
    const apiUrl = window.location.origin + "/api/v1";
    class FormInput {
        constructor() {
            this.raw = null;
            this.dom = null;
        }
        fromHTML(html) {
            this.raw = html;
        }
        createDefault(input_name, { label = "", type = "text", placeholder = "" } = {}) {
            if (label) {
                this.raw = `<label for="${input_name}">${label}</label><input placeholder="${placeholder}" name="${input_name}" type="${type}">`;
            } else {
                this.raw = `<input placeholder="${placeholder}" name="${input_name}" type="${type}">`;
            }
        }
    }
    class FormImage {
        constructor() {
            this.raw = null;
            this.dom = null;
        }
        fromHTML(html) {
            this.raw = html;
        }
        createDefault(src, alt = "") {
            this.raw = `<img src="${src}" alt="${alt}">`;
        }
    }
    class FormHandler {
        constructor() {
            this.title = null;
            this.titleEl = null;
            this.backgroundEl = null;
            this.wrapperEl = null;
            this.formEl = null;
            this.elements = [];
        }
        addInput(input) {
            this.elements.push(input);
        }
        addInputs(inputArray) {
            this.elements = this.elements.concat(inputArray);
        }
        addImage(img) {
            this.elements.push(img);
        }
        addSubmit(buttonText) {
            let el = { raw: `<input class="form-submit" type="submit" value="${buttonText}">`, dom: null };
            this.elements.push(el);
        }
        addText(text) {
            let el = { raw: `<div class="form-text">${text}</div>`, dom: null };
            this.elements.push(el);
        }
        setTitle(title) {
            if (this.titleEl) {
                this.titleEl.innerText = title;
            }
            this.title = title;
        }
        draw() {
            if (!this.backgroundEl) {
                let backgroundEl = document.querySelector("body>.login-form-background");
                if (!backgroundEl) {
                    const emptyTemplate = `<div class="login-form-background"><div class="login-form-wrapper"><form id="login-form"></form></div></div>`;
                    document.body.insertAdjacentHTML("afterbegin", emptyTemplate);
                    backgroundEl = document.querySelector("body>.login-form-background");
                }
                this.backgroundEl = backgroundEl;
                this.wrapperEl = this.backgroundEl.querySelector(".login-form-wrapper");
                this.formEl = this.wrapperEl.getElementsByTagName("form")[0];
                if (this.title) {
                    this.titleEl = document.createElement("div");
                    this.titleEl.className = "login-form-title";
                    this.titleEl.innerText = this.title;
                    this.wrapperEl.insertBefore(this.titleEl, this.formEl);
                }
                this.titleEl = backgroundEl.querySelector(".login-form-title");

            }
            this.drawNewElements();
            this.show();
        }

        drawNewElements(before = null) {
            for (let element of this.elements) {
                if (!element.dom) {
                    let el = document.createElement("div");
                    el.className = "form-block";
                    el.innerHTML = element.raw;
                    element.dom = el;
                    if (before) {
                        this.formEl.insertBefore(el, before.dom);
                    } else {
                        this.formEl.appendChild(el);
                    }
                }
            }
        }
        setSubmitCallback(callback) {
            if (!this.formEl) {
                throw "Form is not drawn";
            }
            this.formEl.onsubmit = (e) => { callback(e, this); };
        }
        removeSubmitCallback() {
            if (!this.formEl) {
                throw "Form is not drawn";
            }
            his.formEl.onsubmit = null;
        }
        removeElement(formElement) {
            this.elements = this.elements.filter(e => e !== formElement);
            formElement.dom.remove();
        }
        clear() {
            for (let element of this.elements) {
                console.log(element);
                if (element.dom) {
                    element.dom.remove();
                }
            }
            this.elements = [];
        }
        show() {
            this.backgroundEl.classList.add("active");
        }
        hide() {
            this.backgroundEl.classList.remove("active");
            this.active = false;
        }
    }

    let notificationHandler = {
        active: false,
        text: null,
        willDisappear: null,
        element: null,
        timer: null
    };

    function showNotification(text, timeout) {
        if (notificationHandler.timer) {
            clearTimeout(notificationHandler.timer);
            notificationHandler.timer = null;
        }
        notificationHandler.active = true;
        notificationHandler.text = text;
        notificationHandler.element.innerText = text;
        notificationHandler.element.classList.add("active");

        if (timeout) {
            notificationHandler.willDisappear = true;
            notificationHandler.timer = setTimeout(() => {
                notificationHandler.active = false;
                notificationHandler.text = null;
                notificationHandler.willDisappear = false;
                notificationHandler.element.classList.remove("active");

            }, timeout);
        } else {
            notificationHandler.willDisappear = false;
        }
    }

    function showLoginForm() {
        let formHandler = new FormHandler();
        formHandler.setTitle("Sign in");

        let login_input = new FormInput();
        let password_input = new FormInput();

        login_input.createDefault("login", {
            label: "Login",
            placeholder: "Login or e-mail"
        });
        password_input.createDefault("password", {
            label: "Password",
            type: "password"
        });

        formHandler.addInputs([login_input, password_input]);
        formHandler.addSubmit("Submit");
        formHandler.draw();

        formHandler.setSubmitCallback((e, formHandler) => {
            const data = new FormData(e.target);
            let allRight = true;
            if (!data.get("login")) {
                e.target.login.style = "outline: 2px solid red;";
                allRight = false;
            }
            if (!data.get("password")) {
                e.target.password.style = "outline: 2px solid red;";
                allRight = false;
            }
            if (allRight) {
                fetch(apiUrl + "/loginKinopoisk", {
                    "method": "POST",
                    "body": data
                }).then(resp => resp.json())
                    .then(resp => {
                        console.log(resp.result);
                        if (resp.result == "ok") {

                        }
                        else if (resp.result == "continue") {
                            continueLogin(resp, formHandler);
                        }
                        else if (resp.result == "error") {
                            showNotification(resp.verbose, 3000);
                        }
                    });
            }

            e.preventDefault();
        });
    }

    function continueLogin(resp, formHandler) {
        if (resp.type == "js-domik-captcha") {
            let captcha_image = new FormImage();
            let captcha_input = new FormInput();
            captcha_image.createDefault("static/img/captcha.jpg");
            captcha_input.createDefault("captcha", {
                placeholder: ""
            });
            let submitEl = formHandler.elements[formHandler.elements.length - 1];
            formHandler.addText("Captcha");
            formHandler.addImage(captcha_image);
            formHandler.addInput(captcha_input);
            formHandler.drawNewElements(submitEl);
            fetch(apiUrl + resp.apiLocation, {
                method: "POST",
                body: JSON.stringify(resp)
            });
        }
    }

    function main() {
        notificationHandler.element = document.getElementById("notification");

        fetch(apiUrl + "/ping", { method: "GET" })
            .then((response) => {
                if (!response.ok) {
                    showNotification("Couldn't connect to Python API server", 0);
                }
            });
        fetch(apiUrl + "/checkKinopoiskAuth", { method: "GET" })
            .then(resp => resp.json())
            .then(resp => {
                if (!resp.auth) {
                    showLoginForm();
                }
            });

    }

    document.addEventListener("DOMContentLoaded", main);
}());