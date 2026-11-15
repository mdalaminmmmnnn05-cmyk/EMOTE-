# ═══════════════════════════════════════════════════════════════
#   RAFIN TxT — LOGIN CORE & UTILS (No Pb2 Version)
# ═══════════════════════════════════════════════════════════════

import asyncio
import random
import json
import os
import time
import uuid
from datetime import datetime

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google_play_scraper import app as play_scraper
from protobuf_decoder.protobuf_decoder import Parser
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'

REGION_LANG = {
    "BD": "bn", "IND": "hi", "PK": "ur", "SG": "en", "ID": "id",
    "ME": "ar", "VN": "vi", "TW": "zh", "CIS": "ru", "TH": "th",
    "EU": "en", "US": "en", "SAC": "es", "LK": "en", "BR": "pt",
}

DEFAULT_HEADERS = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.12f1',
    'X-GA-SV': '1789535859',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB55',
}

# ═══════════════════════════════════════════════════════════════
#              ★ Protobuf ম্যানুয়াল হেল্পার (pb2 ছাড়া) ★
# ═══════════════════════════════════════════════════════════════

def _pb_varint(n):
    if n < 0:
        n = (1 << 64) + n
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)

def _pb_field(f, v):
    if isinstance(v, int):
        return _pb_varint((f << 3) | 0) + _pb_varint(v)
    if isinstance(v, str):
        d = v.encode('utf-8')
        return _pb_varint((f << 3) | 2) + _pb_varint(len(d)) + d
    if isinstance(v, bytes):
        return _pb_varint((f << 3) | 2) + _pb_varint(len(v)) + v
    return b""

def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict):
        return default
    if key in d:
        return d[key].get('data', default)
    if str(key) in d:
        return d[str(key)].get('data', default)
    return default

async def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {"wire_type": result.wire_type}
        if result.wire_type in ("varint", "string", "bytes"):
            field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            if hasattr(result.data, "results"):
                field_data["data"] = await parse_results(result.data.results)
            elif isinstance(result.data, list):
                field_data["data"] = await parse_results(result.data)
            else:
                field_data["data"] = str(result.data)
        result_dict[str(result.field)] = field_data
    return result_dict

# ═══════════════════════════════════════════════════════════════
#              ★ LOGIN ENGINE ★
# ═══════════════════════════════════════════════════════════════

async def get_playstore_version():
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(
            None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='id')
        )
        return res.get("version", "1.132.8")
    except Exception:
        return "1.132.8"

async def version_config(client_http, region="IND"):
    app_version = await get_playstore_version()
    lang = REGION_LANG.get(region, "hi")
    api_url = (
        f"https://version.ggwhitehawk.com/live/ver.php?version={app_version}"
        f"&lang={lang}&device=android&channel=android&appstore=googleplay"
        f"&region={region}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
    )
    try:
        res = await client_http.get(api_url)
        data = res.json()
        return (
            data.get("latest_release_version"),
            data.get("remote_version"),
            data.get("server_url"),
        )
    except Exception:
        return None

async def get_access_token(client_http, uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    data = {
        "uid": str(uid),
        "password": str(password),
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067",
    }
    for attempt in range(3):
        try:
            r = await client_http.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                rd = r.json()
                return rd.get("open_id"), rd.get("access_token"), rd.get("platform", 4)
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return None

async def build_majorlogin_payload(open_id, access_token, platform, client_version):
    try:
        # ম্যানুয়ালি MajorLoginReq তৈরি করা হচ্ছে (pb2 ছাড়া)
        base = b""
        base += _pb_field(3, str(datetime.now())[:-7])
        base += _pb_field(4, "free fire")
        base += _pb_field(5, 1)
        base += _pb_field(7, str(client_version))
        base += _pb_field(8, "Android OS 15 / API-35 (AP3A.240905.015.A2/185014)")
        base += _pb_field(9, "Handheld")
        base += _pb_field(10, "JIO")
        base += _pb_field(11, "WIFI")
        base += _pb_field(12, 1600)
        base += _pb_field(13, 719)
        base += _pb_field(14, "234")
        base += _pb_field(15, "ARM64 FP ASIMD AES | 1820 | 8")
        base += _pb_field(16, 2798)
        base += _pb_field(17, "Mali-G57")
        base += _pb_field(18, "OpenGL ES 3.2 v1.r49p1-04eac0.2848c17a2fd4e9340e06555168eaa3c9")
        base += _pb_field(19, f"Google|{str(uuid.uuid4())}")
        base += _pb_field(20, f"{random.randint(103,223)}.{random.randint(10,250)}.{random.randint(10,250)}.{random.randint(10,250)}")
        base += _pb_field(21, "hi")
        base += _pb_field(22, str(open_id))
        base += _pb_field(23, "4")
        base += _pb_field(24, "Handheld")
        
        # Nested field 25 (memory_available)
        nested = _pb_field(6, 55) + _pb_field(8, 81)
        base += _pb_field(25, nested)
        
        base += _pb_field(29, str(access_token))
        base += _pb_field(30, 1)
        base += _pb_field(41, "JIO")
        base += _pb_field(42, "WIFI")
        base += _pb_field(57, "7428b253defc164018c604a1ebbfebdf")
        base += _pb_field(60, 49973)
        base += _pb_field(61, 11338)
        base += _pb_field(62, 854)
        base += _pb_field(63, 11466)
        base += _pb_field(64, 11466)
        base += _pb_field(65, 49973)
        base += _pb_field(66, 11466)
        base += _pb_field(67, 49973)
        base += _pb_field(73, 2)
        base += _pb_field(74, "/data/app/~~lHFxTCCbupG2QVJmsURtZw==/com.dts.freefireth-N3aCHpHNXpdxjD80uIIbww==/lib/arm64")
        base += _pb_field(76, 1)
        base += _pb_field(77, "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~lHFxTCCbupG2QVJmsURtZw==/com.dts.freefireth-N3aCHpHNXpdxjD80uIIbww==/base.apk")
        base += _pb_field(78, 3)
        base += _pb_field(79, 2)
        base += _pb_field(81, "64")
        base += _pb_field(83, "2019121229")
        base += _pb_field(86, "OpenGLES2")
        base += _pb_field(87, 8191)
        base += _pb_field(88, 4)
        base += _pb_field(92, 15078)
        base += _pb_field(93, "android")
        base += _pb_field(94, "KqsHTx3+QOmBRR1WKvaWewlcpqJBfjki+PPHQoQG8+0yV+Uos7gUFFjHMQ/e7u6han6Fl77r7c3vMN3p8UbKgN+nfycQCgwBmWgBzomx2gj84c+p")
        base += _pb_field(95, 111207)
        base += _pb_field(97, 1)
        base += _pb_field(98, 0)
        base += _pb_field(99, "4")
        base += _pb_field(100, "4")
        
        # Extra fields
        base += _pb_field(96, '{"cur_rate":[90,60,120],"support_etc2":false}')
        base += _pb_field(97, 1)
        base += _pb_field(99, "4")
        base += _pb_field(100, "4")
        base += _pb_field(102, b"\x17]ENWU\x0eR5")
        base += _pb_field(104, 52882)
        base += _pb_field(105, 1)
        base += _pb_field(106, "https://dl.ak.freefiremobile.com/live/ABHotUpdates/|https://core-ak.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462")
        base += _pb_field(107, "c8e41b7a93f02d56e1a94c7b8203f5d1")

        return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(base, 16))
    except Exception as e:
        print(f"Error in payload: {e}")
        return None

async def send_majorlogin(client_http, data, release_version, server_url):
    try:
        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        req_headers = DEFAULT_HEADERS.copy()
        req_headers["ReleaseVersion"] = str(release_version)
        response = await client_http.post(url, headers=req_headers, data=data)
        if response.status_code != 200 or len(response.content) < 40:
            return None
        
        parsed = Parser().parse(response.content.hex())
        dict_res = await parse_results(parsed)

        # ম্যানুয়ালি ডেটা বের করা
        account_uid = get_proto_field(dict_res, 1)
        region = get_proto_field(dict_res, 2)
        token = get_proto_field(dict_res, 8)
        url = get_proto_field(dict_res, 10)
        timestamp = get_proto_field(dict_res, 21, int(time.time()))
        key_val = get_proto_field(dict_res, 22) or AES_KEY
        iv_val = get_proto_field(dict_res, 23) or AES_IV

        if isinstance(key_val, str):
            try: key_val = bytes.fromhex(key_val)
            except Exception: pass
        if isinstance(iv_val, str):
            try: iv_val = bytes.fromhex(iv_val)
            except Exception: pass

        return {
            "account_uid": account_uid,
            "region": region,
            "token": token,
            "url": url or server_url,
            "timestamp": timestamp,
            "key": key_val,
            "iv": iv_val
        }
    except Exception as e:
        print(f"MajorLogin error: {e}")
        return None

async def send_getlogin(client_http, data, base_url, token, release_version):
    try:
        url = f"{base_url.rstrip('/')}/GetLoginData"
        req_headers = DEFAULT_HEADERS.copy()
        req_headers["ReleaseVersion"] = str(release_version)
        req_headers['Authorization'] = f"Bearer {token}"

        response = await client_http.post(url, headers=req_headers, data=data)
        if response.status_code != 200:
            return None

        parsed = Parser().parse(response.content.hex())
        dict_res = await parse_results(parsed)
        return dict_res
    except Exception as e:
        print(f"GetLoginData error: {e}")
        return None

async def do_login(uid, password, region_pref="IND"):
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client_http:
        vc = await version_config(client_http, region_pref)
        if not vc:
            print("[ERROR] ভার্সন কনফিগ ব্যর্থ হয়েছে।")
            return None
        release_version, client_version, server_url = vc
        print(f"[OK] ভার্সন : {client_version} │ রিলিজ : {release_version}")

        tg = await get_access_token(client_http, uid, password)
        if not tg:
            print("[ERROR] UID বা পাসওয়ার্ড ভুল — অ্যাক্সেস টোকেন পাওয়া যায়নি।")
            return None
        open_id, access_token, platform = tg
        print("[OK] অ্যাক্সেস টোকেন সফলভাবে পাওয়া গেছে।")

        payload = await build_majorlogin_payload(open_id, access_token, platform, client_version)
        if not payload:
            print("[ERROR] পেলোড তৈরি ব্যর্থ হয়েছে।")
            return None

        major_res = await send_majorlogin(client_http, payload, release_version, server_url)
        if not major_res or not major_res.get("account_uid"):
            print("[ERROR] MajorLogin সার্ভার দ্বারা প্রত্যাখ্যাত হয়েছে।")
            return None
        print(f"[OK] অ্যাকাউন্ট UID গৃহীত : {major_res['account_uid']}")

        gl = await send_getlogin(client_http, payload, major_res["url"], major_res["token"], release_version)
        if not gl:
            print("[ERROR] GetLoginData ব্যর্থ হয়েছে।")
            return None
        dict_res = gl
        print("[OK] লগইন তথ্য সফলভাবে গৃহীত হয়েছে।")

        online_addr = get_proto_field(dict_res, 14, "0.0.0.0:0")
        if ':' in str(online_addr):
            online_ip, online_port = str(online_addr).split(":")
        else:
            online_ip, online_port = "0.0.0.0", "0"

        chat_addr = get_proto_field(dict_res, 32, online_addr)
        if ':' in str(chat_addr):
            chat_ip, chat_port = str(chat_addr).split(":")
        else:
            chat_ip, chat_port = online_ip, online_port

        return {
            "bot_uid":      str(major_res["account_uid"]),
            "token":        major_res["token"],
            "region":       major_res["region"] or region_pref,
            "key":          major_res["key"],
            "iv":           major_res["iv"],
            "timestamp":    major_res["timestamp"],
            "online_ip":    online_ip,
            "online_port":  online_port,
            "chat_ip":      chat_ip,
            "chat_port":    chat_port,
            "account_name": get_proto_field(dict_res, 1, "Unknown"),
            "clan_id":      get_proto_field(dict_res, 2, 0),
            "clan_data":    get_proto_field(dict_res, 3, ""),
            "server_url":   major_res["url"],
        }