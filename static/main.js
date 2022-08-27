let host = window.location.host;
var uuid_lookuptable = []; for (var i = 0; i < 256; i++) { uuid_lookuptable[i] = (i < 16 ? '0' : '') + (i).toString(16); }
function uuid4() {
    var d0 = Math.random() * 0xffffffff | 0;
    var d1 = Math.random() * 0xffffffff | 0;
    var d2 = Math.random() * 0xffffffff | 0;
    var d3 = Math.random() * 0xffffffff | 0;
    return uuid_lookuptable[d0 & 0xff] + uuid_lookuptable[d0 >> 8 & 0xff] + uuid_lookuptable[d0 >> 16 & 0xff] + uuid_lookuptable[d0 >> 24 & 0xff] + '-' +
        uuid_lookuptable[d1 & 0xff] + uuid_lookuptable[d1 >> 8 & 0xff] + '-' + uuid_lookuptable[d1 >> 16 & 0x0f | 0x40] + uuid_lookuptable[d1 >> 24 & 0xff] + '-' +
        uuid_lookuptable[d2 & 0x3f | 0x80] + uuid_lookuptable[d2 >> 8 & 0xff] + '-' + uuid_lookuptable[d2 >> 16 & 0xff] + uuid_lookuptable[d2 >> 24 & 0xff] +
        uuid_lookuptable[d3 & 0xff] + uuid_lookuptable[d3 >> 8 & 0xff] + uuid_lookuptable[d3 >> 16 & 0xff] + uuid_lookuptable[d3 >> 24 & 0xff];
}

let test = "https://strm.yandex.ru/vh-ottenc-converted/vod-content/4d8e77796bc0a8f199b48f1b408ecdde/8859010x1637749503x290129bd-7e37-4db1-87c8-e5a5a4245e06/dash-cenc/ysign1=625a47406912e907cec65cdebb99c84b854f416f3d8f1c4ec1b3bf227166f6cc,abcID=1358,from=ott-kp,pfx,sfx,ts=630c8dd1/sdr_hd_avc_aac.mpd?ottsession=e5a6290b0a3d4eadb2c3ca936ac4047c&testid=633106&testid=628191"
let manifestUri = "https://" + host + "/manifest?url=" + encodeURIComponent(test)
function initApp() {
    // Install built-in polyfills to patch browser incompatibilities.
    shaka.polyfill.installAll();
    // Check to see if the browser supports the basic APIs Shaka needs.
    if (shaka.Player.isBrowserSupported()) {
        // Everything looks good!
        initPlayer();
    } else {
        // This browser does not have the minimum set of APIs we need.
        // alert('Browser not supported!');
        console.log("Browser not supported")
    }
}
async function initPlayer() {
    // Create a Player instance.
    const video = document.getElementById('video');
    const player = new shaka.Player(video);
    player.configure({
        streaming: {
            bufferingGoal: 1,
            retryParameters: {
                maxAttempts: 10,
                stallTimeout: 0,
                timeout: 1000,
                connectionTimeout: 0
            }
        }
    });
    // player.regis
    const videoWrapper = document.getElementById("videoWrapper")
    const ui = new shaka.ui.Overlay(player, videoWrapper,
        video);
    const config = {
        'controlPanelElements': ['quality', 'language', 'captions', 'fullscreen']
    };
    ui.configure(config);

    player.configure({
        drm: {
            servers: {
                'com.widevine.alpha': 'https://widevine-proxy.ott.yandex.ru/proxy'
            },
        }
    });

    player.getNetworkingEngine().registerRequestFilter(function (type, request) {
        if (type == shaka.net.NetworkingEngine.RequestType.LICENSE) {
            // redirect to our server
            request.uris[0] = "https://" + host + "/drm?url=" + encodeURIComponent(request.uris[0])
            b64encoded = request.body
            request.body = JSON.stringify({
                   "puid": 426134986,
                    "watchSessionId": "78cba1e69d4744afa59aa3eddac27c80",
                    "contentId": "4d8e77796bc0a8f199b48f1b408ecdde",
                    "contentTypeId": 21,
                    "serviceName": "ott-kp",
                    "productId": 2,
                    "monetizationModel": "SVOD",
                    "expirationTimestamp": 1661383520,
                    "verificationRequired": true,
                    "signature": "f4165e89d1ce057e522db4d23f5b6fb14d8da76a",
                    "version": "V4",
                "rawLicenseRequestBase64": shaka.util.Uint8ArrayUtils.toBase64(new Uint8Array(request.body))
            })
        } else if (type == shaka.net.NetworkingEngine.RequestType.SEGMENT) {
            for (let i = 0; i < request.uris.length; i++) {
                request.uris[i] = "https://" + host + "/segment?url=" + encodeURIComponent(request.uris[i]);
                request.headers["X-Request-Id"] = uuid4()
            }
        }
    })

    // Attach player to the window to make it easy to access in the JS console.
    window.player = player;

    // Listen for error events.
    player.addEventListener('error', onErrorEvent);

    // Try to load a manifest.
    // This is an asynchronous process.
    try {
        await player.load(manifestUri);
        // This runs if the asynchronous load is successful.
        console.log('The video has now been loaded!');
    } catch (e) {
        // onError is executed if the asynchronous load fails.
        onError(e);
    }
}
function onErrorEvent(event) {
    // Extract the shaka.util.Error object from the event.
    // fetch('/error', {
    //     'method': 'POST',
    //     'body': JSON.stringify(error)
    // })
    onError(event.detail);
}

function onError(error) {
    // Log the error.
    console.error('Error code', error.code, 'object', error);
    // fetch('/error', {
    //     'method': 'POST',
    //     'body': JSON.stringify(error)
    // })
}

// window.addEventListener("keydown", function (e) {
//     fetch('/error', {
//         'method': 'POST',
//         'body': JSON.stringify(e.code)
//     })
// });

document.addEventListener("DOMContentLoaded", (e) => {
    initApp();
})
