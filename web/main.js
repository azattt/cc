let filterLicenseRequest = function (request) {
    console.log('LICENSE REQUEST', request);
    /* Here you can modify/overwrite the licens request (url, headers, data...) */
    request.headers = {
        "X-AxDRM-Message": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ2ZXJzaW9uIjoxLCJjb21fa2V5X2lkIjoiYjMzNjRlYjUtNTFmNi00YWUzLThjOTgtMzNjZWQ1ZTMxYzc4IiwibWVzc2FnZSI6eyJ0eXBlIjoiZW50aXRsZW1lbnRfbWVzc2FnZSIsImZpcnN0X3BsYXlfZXhwaXJhdGlvbiI6NjAsInBsYXlyZWFkeSI6eyJyZWFsX3RpbWVfZXhwaXJhdGlvbiI6dHJ1ZX0sImtleXMiOlt7ImlkIjoiOWViNDA1MGQtZTQ0Yi00ODAyLTkzMmUtMjdkNzUwODNlMjY2IiwiZW5jcnlwdGVkX2tleSI6ImxLM09qSExZVzI0Y3Iya3RSNzRmbnc9PSJ9XX19.FAbIiPxX8BHi9RwfzD7Yn-wugU19ghrkBFKsaCPrZmU",
        "Content-Type": "application/json",
        'Access-Control-Allow-Origin': '*'
    }
    let utf8Encode = new TextEncoder();
    request.data = utf8Encode.encode(JSON.stringify({
        "puid": 426134986,
        "watchSessionId": "7090c1433b3b4dfdb24b54cd56cf68bf",
        "contentId": "4d8e77796bc0a8f199b48f1b408ecdde",
        "contentTypeId": 21,
        "serviceName": "ott-kp",
        "productId": 2,
        "monetizationModel": "SVOD",
        "expirationTimestamp": 1660780482,
        "verificationRequired": true,
        "signature": "560c4b8a0251188d60a00331a92f11862640bb75",
        "version": "V4"
    }))
    console.log(request);
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
let test = "https://strm.yandex.ru/vh-ottenc-converted/vod-content/4d8e77796bc0a8f199b48f1b408ecdde/8859010x1637749503x290129bd-7e37-4db1-87c8-e5a5a4245e06/dash-cenc/ysign1=7ee30d6adf8907b489d2c5dd6417bded9bec8ecfe717b96f07c3124a84f2a06a,abcID=1358,from=ott-kp,pfx,sfx,ts=630a991a/sdr_hd_avc_aac.mpd?ottsession=e5349d27f3f6444fa3fdfd7da1f3fc9f&testid=632399&testid=633106&testid=628191"
player.initialize(document.querySelector("video"), test, true);