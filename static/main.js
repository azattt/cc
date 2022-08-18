function fromCharCodeimpl() {
    /** @param {number} size @return {boolean} */
    const supportsChunkSize = (size) => {
        try {
            // The compiler will complain about suspicious value if this isn't
            // stored in a variable and used.
            const buffer = new Uint8Array(size);
            // This can't use the spread operator, or it blows up on Xbox One.
            // So we use apply() instead, which is normally not allowed.
            // See issue #2186 for more details.
            // eslint-disable-next-line no-restricted-syntax
            const foo = String.fromCharCode.apply(null, buffer);
            return foo.length > 0; // Actually use "foo", so it's not compiled out.
        } catch (error) {
            return false;
        }
    };
    // Different browsers support different chunk sizes; find out the largest
    // this browser supports so we can use larger chunks on supported browsers
    // but still support lower-end devices that require small chunks.
    // 64k is supported on all major desktop browsers.
    for (let size = 64 * 1024; size > 0; size /= 2) {
        if (supportsChunkSize(size)) {
            return (buffer) => {
                let ret = '';
                for (let i = 0; i < buffer.length; i += size) {
                    const subArray = buffer.subarray(i, i + size);
                    // This can't use the spread operator, or it blows up on Xbox One.
                    // So we use apply() instead, which is normally not allowed.
                    // See issue #2186 for more details.
                    // eslint-disable-next-line no-restricted-syntax
                    ret += String.fromCharCode.apply(null, subArray);  // Issue #2186
                }
                return ret;
            };
        }
    }
    return null;
}
function fromCharCode(array) {
    return fromCharCodeimpl()(array);
}

function unsafeGetArrayBuffer_(view) {
    if (view instanceof ArrayBuffer) {
        return view;
    } else {
        return view.buffer;
    }
}
function view_(data, offset, length, Type) {
    const buffer = unsafeGetArrayBuffer_(data);
    // Absolute end of the |data| view within |buffer|.
    /** @suppress {strictMissingProperties} */
    const dataEnd = (data.byteOffset || 0) + data.byteLength;
    // Absolute start of the result within |buffer|.
    /** @suppress {strictMissingProperties} */
    const rawStart = (data.byteOffset || 0) + offset;
    const start = Math.max(0, Math.min(rawStart, dataEnd));
    // Absolute end of the result within |buffer|.
    const end = Math.min(start + Math.max(length, 0), dataEnd);
    return new Type(buffer, start, end - start);
}

function toUint8(data, offset = 0, length = Infinity) {
    return view_(data, offset, length, Uint8Array);
}

function toStandardBase64(data) {
    const bytes = fromCharCode(
        toUint8(data));
    return btoa(bytes);
}
function toBase64(data, padding) {
    padding = (padding == undefined) ? true : padding;
    const base64 = toStandardBase64(data)
        .replace(/\+/g, '-').replace(/\//g, '_');
    return padding ? base64 : base64.replace(/[=]*$/, '');
}

let filterLicenseRequest = function (request) {
    console.log(request.data)
    request.headers = {
        "Content-Type": "application/json"
    }
    request.url = "/drm?url=" + encodeURIComponent(request.url)
    let utf8Encode = new TextEncoder();
    const b64encoded = toBase64(request.data)
    request.data = utf8Encode.encode(JSON.stringify({
        "puid": 426134986,
        "watchSessionId": "6f414ffbdc7c41b2a9e4b57e3b60ddfa",
        "contentId": "4d8e77796bc0a8f199b48f1b408ecdde",
        "contentTypeId": 21,
        "serviceName": "ott-kp",
        "productId": 2,
        "monetizationModel": "SVOD",
        "expirationTimestamp": 1660868561,
        "verificationRequired": true,
        "signature": "e31acdd9598da46a05033591c96a11de944d02bf",
        "version": "V4",
        "rawLicenseRequestBase64": b64encoded
    }))
    console.log(b64encoded)
    return Promise.resolve();
}

let filterLicenseResponse = function (response) {
    return Promise.resolve();
}


let player = dashjs.MediaPlayer().create();
const protData = {
    "com.widevine.alpha": {
        "serverURL": "https://widevine-proxy.ott.yandex.ru/proxy"
    },
};

player.setProtectionData(protData);

player.registerLicenseRequestFilter(filterLicenseRequest);
player.registerLicenseResponseFilter(filterLicenseResponse);
let main = "/dash?url="
let test = "https://strm.yandex.ru/vh-ottenc-converted/vod-content/4d8e77796bc0a8f199b48f1b408ecdde/8859010x1637749503x290129bd-7e37-4db1-87c8-e5a5a4245e06/dash-cenc/ysign1=8041346f8e0edbc86108d9350245c9b12f6a3c0e44f1d65690e9eb2e20e4d8f9,abcID=1358,from=ott-kp,pfx,sfx,ts=630bb271/sdr_hd_avc_aac.mpd?ottsession=6f414ffbdc7c41b2a9e4b57e3b60ddfa&testid=632399&testid=633106&testid=628191"
//main = "/lotofdata?url="
player.initialize(document.querySelector("video"), main + encodeURIComponent(test), true);