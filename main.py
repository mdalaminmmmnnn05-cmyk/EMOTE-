# ═══════════════════════════════════════════════════════════════
#   RAFIN TxT — ALL-IN-ONE EMOTE WEB SERVER
# ═══════════════════════════════════════════════════════════════

import asyncio
import time
import os
import random
import uuid
from datetime import datetime
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import httpx
from google_play_scraper import app as play_scraper
from protobuf_decoder.protobuf_decoder import Parser

# ─── আপনার অন্যান্য মডিউল ───
from xC4 import Emote_k, JoinSquadByTeamCode
# যদি Pb2 ফোল্ডার থাকে, তবে নিচের লাইনগুলো কাজ করবে, না থাকলে কমেন্ট আউট করুন
try:
    from Pb2 import MajoRLoGinrEs_pb2, PorTs_pb2, MajoRLoGinrEq_pb2
except ImportError:
    pass

app = FastAPI(title="RAFIN TxT Emote Web")

# ═══════════════════════════════════════════════════════════════
#              ★ লগইন ইঞ্জিন (একই ফাইলে) ★
# ═══════════════════════════════════════════════════════════════

AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV  = b'6oyZDr22E3ychjM%'
REGION_LANG = {"BD": "bn", "IND": "hi", "PK": "ur", "SG": "en", "ID": "id", "ME": "ar"}

DEFAULT_HEADERS = {
    'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded', 'Expect': '100-continue',
    'X-Unity-Version': '2018.4.12f1', 'X-GA-SV': '1789535859',
    'X-GA': 'v1 1', 'ReleaseVersion': 'OB55',
}

def _pb_varint(n):
    if n < 0: n = (1 << 64) + n
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def _pb_field(f, v):
    if isinstance(v, int): return _pb_varint((f << 3) | 0) + _pb_varint(v)
    if isinstance(v, str):
        d = v.encode('utf-8')
        return _pb_varint((f << 3) | 2) + _pb_varint(len(d)) + d
    if isinstance(v, bytes): return _pb_varint((f << 3) | 2) + _pb_varint(len(v)) + v
    return b""

def get_proto_field(d, key, default=None):
    if not d or not isinstance(d, dict): return default
    if key in d: return d[key].get('data', default)
    if str(key) in d: return d[str(key)].get('data', default)
    return default

async def parse_results(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {"wire_type": result.wire_type}
        if result.wire_type in ("varint", "string", "bytes"): field_data["data"] = result.data
        elif result.wire_type == "length_delimited":
            if hasattr(result.data, "results"): field_data["data"] = await parse_results(result.data.results)
            elif isinstance(result.data, list): field_data["data"] = await parse_results(result.data)
            else: field_data["data"] = str(result.data)
        result_dict[str(result.field)] = field_data
    return result_dict

async def get_playstore_version():
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, lambda: play_scraper('com.dts.freefireth', lang='hi', country='id'))
        return res.get("version", "1.132.8")
    except Exception: return "1.132.8"

async def version_config(client_http, region="IND"):
    app_version = await get_playstore_version()
    lang = REGION_LANG.get(region, "hi")
    api_url = f"https://version.ggwhitehawk.com/live/ver.php?version={app_version}&lang={lang}&device=android&channel=android&appstore=googleplay&region={region}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0"
    try:
        res = await client_http.get(api_url)
        data = res.json()
        return (data.get("latest_release_version"), data.get("remote_version"), data.get("server_url"))
    except Exception: return None

async def get_access_token(client_http, uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    hdrs = {"Host": "100067.connect.garena.com", "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; SM-G998B Build/SP1A.210812.016)", "Content-Type": "application/x-www-form-urlencoded", "Accept-Encoding": "gzip, deflate, br", "Connection": "close"}
    data = {"uid": str(uid), "password": str(password), "response_type": "token", "client_type": "2", "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3", "client_id": "100067"}
    for attempt in range(3):
        try:
            r = await client_http.post(url, headers=hdrs, data=data)
            if r.status_code == 200:
                rd = r.json()
                return rd.get("open_id"), rd.get("access_token"), rd.get("platform", 4)
        except Exception: pass
        await asyncio.sleep(0.5)
    return None

async def build_payload(open_id, access_token, platform, client_version):
    try:
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
        base += _pb_field(18, "OpenGL ES 3.2 v1.r49p1")
        base += _pb_field(19, f"Google|{str(uuid.uuid4())}")
        base += _pb_field(20, f"{random.randint(103,223)}.{random.randint(10,250)}.{random.randint(10,250)}.{random.randint(10,250)}")
        base += _pb_field(21, "hi")
        base += _pb_field(22, str(open_id))
        base += _pb_field(23, "4")
        base += _pb_field(24, "Handheld")
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
        base += _pb_field(96, '{"cur_rate":[90,60,120],"support_etc2":false}')
        base += _pb_field(102, b"\x17]ENWU\x0eR5")
        base += _pb_field(104, 52882)
        base += _pb_field(105, 1)
        base += _pb_field(106, "https://dl.ak.freefiremobile.com/live/ABHotUpdates/|https://core-ak.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462")
        base += _pb_field(107, "c8e41b7a93f02d56e1a94c7b8203f5d1")
        return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(base, 16))
    except Exception: return None

async def do_login(uid, password, region_pref="IND"):
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client_http:
        vc = await version_config(client_http, region_pref)
        if not vc: return None
        release_version, client_version, server_url = vc
        tg = await get_access_token(client_http, uid, password)
        if not tg: return None
        open_id, access_token, platform = tg
        payload = await build_payload(open_id, access_token, platform, client_version)
        if not payload: return None

        url = f"{server_url}MajorLogin" if server_url.endswith('/') else f"{server_url}/MajorLogin"
        req_headers = DEFAULT_HEADERS.copy()
        req_headers["ReleaseVersion"] = str(release_version)
        response = await client_http.post(url, headers=req_headers, data=payload)
        
        if response.status_code != 200 or len(response.content) < 40: return None
        
        parsed = Parser().parse(response.content.hex())
        dict_res = await parse_results(parsed)

        account_uid = get_proto_field(dict_res, 1)
        region = get_proto_field(dict_res, 2)
        token = get_proto_field(dict_res, 8)
        url_res = get_proto_field(dict_res, 10)
        timestamp = get_proto_field(dict_res, 21, int(time.time()))
        key_val = get_proto_field(dict_res, 22) or AES_KEY
        iv_val = get_proto_field(dict_res, 23) or AES_IV

        if not account_uid or not token: return None

        if isinstance(key_val, str):
            try: key_val = bytes.fromhex(key_val)
            except Exception: pass
        if isinstance(iv_val, str):
            try: iv_val = bytes.fromhex(iv_val)
            except Exception: pass

        # GetLoginData (IP/Port)
        url2 = f"{url_res.rstrip('/')}/GetLoginData"
        req_headers['Authorization'] = f"Bearer {token}"
        response2 = await client_http.post(url2, headers=req_headers, data=payload)
        
        online_ip, online_port = "0.0.0.0", "0"
        if response2.status_code == 200:
            parsed2 = Parser().parse(response2.content.hex())
            dict_res2 = await parse_results(parsed2)
            addr = get_proto_field(dict_res2, 14, "0.0.0.0:0")
            if ':' in str(addr):
                online_ip, online_port = str(addr).split(":")
            else:
                online_ip, online_port = "0.0.0.0", "0"

        return {
            "bot_uid": str(account_uid), "token": token,
            "region": region or region_pref, "key": key_val, "iv": iv_val,
            "timestamp": timestamp, "online_ip": online_ip, "online_port": online_port,
        }

# ═══════════════════════════════════════════════════════════════
#              ★ ওয়েবসাইট কনফিগারেশন ★
# ═══════════════════════════════════════════════════════════════

BOT_UID = os.getenv("BOT_UID", "8437458863")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "99A4B0B655293F4F087B5ECC22084DCC7475677E929868FB89549F326F9FFBE1")
BOT_REGION = os.getenv("BOT_REGION", "BD")
_SESSION = {"data": None, "ts": 0}

async def get_bot_session():
    now = time.time()
    if _SESSION["data"] and (now - _SESSION["ts"] < 5 * 3600): return _SESSION["data"]
    result = await do_login(BOT_UID, BOT_PASSWORD, BOT_REGION)
    if not result: raise HTTPException(500, "বট লগইন ব্যর্থ — UID/Password চেক করুন")
    _SESSION["data"] = result
    _SESSION["ts"] = now
    return result

def build_auth_packet(account_uid, token, timestamp, key, iv):
    if isinstance(key, str): key = bytes.fromhex(key)
    if isinstance(iv, str): iv = bytes.fromhex(iv)
    token_bytes = token.encode("utf-8")
    ct = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(token_bytes, 16))
    opcode = bytes.fromhex("830c")
    uid_b = int(account_uid).to_bytes(8, "big")
    ts_b = int(timestamp).to_bytes(4, "big")
    len_b = len(ct).to_bytes(8, "big")
    return opcode + uid_b + ts_b + len_b + ct

async def send_packets_tcp(sess, packets: list, wait_between=0.5):
    ip = sess["online_ip"]
    port = int(sess["online_port"])
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=10)
    except Exception as e:
        return False, f"TCP কানেকশন ব্যর্থ: {e}"
    try:
        auth = build_auth_packet(sess["bot_uid"], sess["token"], sess["timestamp"], sess["key"], sess["iv"])
        writer.write(auth)
        await writer.drain()
        await asyncio.sleep(0.8)
        for pkt in packets:
            if pkt is None: continue
            if isinstance(pkt, str): pkt = bytes.fromhex(pkt)
            writer.write(pkt)
            await writer.drain()
            await asyncio.sleep(wait_between)
        return True, "প্যাকেট পাঠানো সম্পন্ন"
    except Exception as e:
        return False, f"Send error: {e}"
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception: pass

# ═══════════════════════════════════════════════════════════════
#              ★ HTML এবং API রুট ★
# ═══════════════════════════════════════════════════════════════

HTML_PAGE = """
<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAFIN TxT — Emote Sender</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 20px;
  }
  .card {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 35px 30px;
    width: 100%; max-width: 420px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }
  h1 {
    text-align: center;
    background: linear-gradient(90deg, #ff6b6b, #feca57, #48dbfb);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 26px; margin-bottom: 8px;
  }
  .sub {
    text-align: center; color: #aaa;
    font-size: 12px; margin-bottom: 28px;
  }
  label {
    display: block; color: #ddd;
    font-size: 13px; margin-bottom: 6px; margin-top: 16px;
    font-weight: 500;
  }
  input {
    width: 100%; padding: 13px 15px;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 10px; color: #fff; font-size: 15px;
    outline: none; transition: 0.2s;
  }
  input:focus {
    border-color: #48dbfb;
    background: rgba(72,219,251,0.1);
  }
  input::placeholder { color: #666; }
  button {
    width: 100%; margin-top: 26px; padding: 14px;
    background: linear-gradient(90deg, #ff6b6b, #feca57);
    border: none; border-radius: 10px;
    color: #111; font-weight: 700; font-size: 16px;
    cursor: pointer; transition: 0.2s;
  }
  button:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(254,202,87,0.4); }
  button:active { transform: scale(0.97); }
  button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
  #result {
    margin-top: 20px; padding: 14px; border-radius: 10px;
    font-size: 13px; line-height: 1.6; display: none;
    word-break: break-all;
  }
  .ok  { background: rgba(46,213,115,0.15); border: 1px solid #2ed573; color: #2ed573; }
  .err { background: rgba(255,71,87,0.15);  border: 1px solid #ff4757; color: #ff4757; }
  .footer { text-align:center; color:#666; font-size:11px; margin-top:22px; }
</style>
</head>
<body>
  <div class="card">
    <h1>🎭 Emote Sender</h1>
    <p class="sub">RAFIN TxT — Premium Emote Engine</p>
    <form id="f">
      <label>🔑 টিম কোড (Squad Code)</label>
      <input name="team_code" placeholder="যেমন: 12345678" required maxlength="12" inputmode="numeric">
      <label>👤 টার্গেট UID</label>
      <input name="target_uid" placeholder="যেমন: 987654321" required maxlength="15" inputmode="numeric">
      <label>🎬 ইমোট ID</label>
      <input name="emote_id" placeholder="যেমন: 909000027" required maxlength="12" inputmode="numeric">
      <button type="submit" id="btn">ইমোট পাঠাও</button>
    </form>
    <div id="result"></div>
    <div class="footer">Dev: RAFIN TxT</div>
  </div>
<script>
const form = document.getElementById('f');
const btn  = document.getElementById('btn');
const res  = document.getElementById('result');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  btn.disabled = true;
  btn.innerHTML = 'পাঠানো হচ্ছে...';
  res.style.display = 'none';
  const fd = new FormData(form);
  try {
    const r = await fetch('/send', { method: 'POST', body: fd });
    const data = await r.json();
    res.style.display = 'block';
    if (r.ok && data.status === 'success') {
      res.className = 'ok';
      res.innerHTML = '✅ <b>সফল!</b><br>' + (data.message || '');
    } else {
      res.className = 'err';
      res.innerHTML = '❌ <b>ব্যর্থ!</b><br>' + (data.detail || 'কিছু ভুল হয়েছে');
    }
  } catch (err) {
    res.style.display = 'block';
    res.className = 'err';
    res.innerHTML = '❌ নেটওয়ার্ক সমস্যা: ' + err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'ইমোট পাঠাও';
  }
});
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home(): return HTML_PAGE

@app.post("/send")
async def send_emote(team_code: str = Form(...), target_uid: str = Form(...), emote_id: str = Form(...)):
    if not team_code.isdigit() or not target_uid.isdigit() or not emote_id.isdigit():
        raise HTTPException(400, "সব ঘরে শুধু সংখ্যা দিন")
    try:
        sess = await get_bot_session()
        join_pkt = await JoinSquadByTeamCode(team_code.strip(), sess["key"], sess["iv"], sess["region"])
        emote_pkt = await Emote_k(target_uid.strip(), emote_id.strip(), sess["key"], sess["iv"], sess["region"])
        ok, msg = await send_packets_tcp(sess, [join_pkt, emote_pkt], wait_between=1.5)
        if not ok: return JSONResponse(status_code=500, content={"status": "error", "detail": msg})
        return JSONResponse({"status": "success", "message": f"টিম <b>{team_code}</b> এ জয়েন করা হয়েছে<br>UID <b>{target_uid}</b> → ইমোট <b>{emote_id}</b> পাঠানো হয়েছে<br>"})
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f"সার্ভার এরর: {e}")

@app.get("/health")
async def health(): return {"status": "ok", "time": int(time.time())}