# ═══════════════════════════════════════════════════════════════
#   RAFIN TxT — EMOTE WEB SERVER (FULL)
# ═══════════════════════════════════════════════════════════════

import asyncio
import time
import os
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ─── আপনার মডিউলগুলো ───
# যেহেতু আপনি নতুন লগইন কোড বানিয়েছেন, তাই login_engine থেকে ইম্পোর্ট করুন
from login_engine import do_login 
from xC4 import Emote_k, JoinSquadByTeamCode

app = FastAPI(title="RAFIN TxT Emote Web")

# ═══════════════════════════════════════════════════════════════
#              ★ কনফিগারেশন ★
# ═══════════════════════════════════════════════════════════════

# Render-এর Environment Variables থেকে ভ্যালু নেবে, না থাকলে ডিফল্ট ব্যবহার করবে
BOT_UID      = os.getenv("BOT_UID", "8437458863")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "99A4B0B655293F4F087B5ECC22084DCC7475677E929868FB89549F326F9FFBE1")
BOT_REGION   = os.getenv("BOT_REGION", "BD") # আপনার বটের রিজিয়ন (BD, IND, PK) দিন

_SESSION = {"data": None, "ts": 0}

# ═══════════════════════════════════════════════════════════════
#              ★ বট লগইন (ক্যাশ) ★
# ═══════════════════════════════════════════════════════════════

async def get_bot_session():
    now = time.time()
    if _SESSION["data"] and (now - _SESSION["ts"] < 5 * 3600):
        return _SESSION["data"]

    # লগইন ইঞ্জিন কল করা হচ্ছে
    result = await do_login(BOT_UID, BOT_PASSWORD, BOT_REGION)
    if not result:
        raise HTTPException(500, "বট লগইন ব্যর্থ — UID/Password অথবা Region ভুল হতে পারে")

    _SESSION["data"] = result
    _SESSION["ts"] = now
    return result

# ═══════════════════════════════════════════════════════════════
#              ★ TCP AUTH PACKET ★
# ═══════════════════════════════════════════════════════════════

def build_auth_packet(account_uid, token, timestamp, key, iv):
    if isinstance(key, str):
        key = bytes.fromhex(key)
    if isinstance(iv, str):
        iv = bytes.fromhex(iv)

    token_bytes = token.encode("utf-8")
    ct = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(token_bytes, 16))

    opcode = bytes.fromhex("830c")
    uid_b = int(account_uid).to_bytes(8, "big")
    ts_b = int(timestamp).to_bytes(4, "big")
    len_b = len(ct).to_bytes(8, "big")
    return opcode + uid_b + ts_b + len_b + ct

# ═══════════════════════════════════════════════════════════════
#              ★ TCP SEND ★
# ═══════════════════════════════════════════════════════════════

async def send_packets_tcp(sess, packets: list, wait_between=0.5):
    ip = sess["online_ip"]
    port = int(sess["online_port"])

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=10
        )
    except Exception as e:
        return False, f"TCP কানেকশন ব্যর্থ: {e}"

    try:
        auth = build_auth_packet(
            sess["bot_uid"], sess["token"],
            sess["timestamp"], sess["key"], sess["iv"]
        )
        writer.write(auth)
        await writer.drain()
        await asyncio.sleep(0.8)

        for pkt in packets:
            if pkt is None:
                continue
            if isinstance(pkt, str):
                pkt = bytes.fromhex(pkt)
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
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
#              ★ HTML ফর্ম ★
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
async def home():
    return HTML_PAGE

# ═══════════════════════════════════════════════════════════════
#              ★ FORM SUBMIT ★
# ═══════════════════════════════════════════════════════════════

@app.post("/send")
async def send_emote(
    team_code: str = Form(...),
    target_uid: str = Form(...),
    emote_id: str = Form(...),
):
    team_code = team_code.strip()
    target_uid = target_uid.strip()
    emote_id = emote_id.strip()

    if not team_code.isdigit():
        raise HTTPException(400, "টিম কোড শুধু সংখ্যা হবে")
    if not target_uid.isdigit():
        raise HTTPException(400, "UID শুধু সংখ্যা হবে")
    if not emote_id.isdigit():
        raise HTTPException(400, "ইমোট ID শুধু সংখ্যা হবে")

    try:
        # ১. বট লগইন
        sess = await get_bot_session()

        # ২. টিম কোডে জয়েন করার প্যাকেট
        join_pkt = await JoinSquadByTeamCode(
            team_code, sess["key"], sess["iv"], sess["region"]
        )

        # ৩. ইমোট প্যাকেট (এখানে সব ডেটা টাইপ ঠিক করা হয়েছে)
        emote_pkt = await Emote_k(
            int(target_uid),
            int(emote_id),
            sess["key"],
            sess["iv"],
            sess["region"],
        )

        # ৪. TCP দিয়ে সার্ভারে পাঠানো
        ok, msg = await send_packets_tcp(
            sess,
            [join_pkt, emote_pkt],
            wait_between=1.5,
        )

        if not ok:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "detail": msg},
            )

        return JSONResponse({
            "status": "success",
            "message": (
                f"টিম <b>{team_code}</b> এ জয়েন করা হয়েছে<br>"
                f"UID <b>{target_uid}</b> → ইমোট <b>{emote_id}</b> পাঠানো হয়েছে<br>"
            ),
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"সার্ভার এরর: {e}")

@app.get("/health")
async def health():
    return {"status": "ok", "time": int(time.time())}