#!/usr/bin/env python3
"""
ICT PRO BOT V7.4 - FULL AUTO Upstox + SL/TP/PARTIAL/REVERSAL + Token Auto + Telegram + State Persistence
Optimized for Render.com | Full Lifecycle Order Management | Matches Pine Script V7.4 Webhook Format
"""

from flask import Flask, request, jsonify, redirect
import requests
import json
from datetime import datetime
import logging
import os
from threading import Thread
import time
import signal
import sys

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Environment Variables (Render.com में सेट करें)
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else ""

# Upstox Credentials
UPSTOX_API_KEY = os.environ.get("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.environ.get("UPSTOX_API_SECRET")
UPSTOX_REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI", "https://your-render-url.onrender.com/callback")

# Global State
access_token = None
token_generated_at = None
active_positions = {}  # symbol → full state dict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ict-pro-bot-v7-4-full-lifecycle'

# Logging
if not os.path.exists("logs"):
    os.makedirs("logs")
logging.basicConfig(
    filename=f"logs/trade_log_{datetime.now().strftime('%Y%m%d')}.txt",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
def save_positions():
    try:
        with open("positions.json", "w") as f:
            json.dump(active_positions, f)
        logger.info("Positions saved to disk")
    except Exception as e:
        logger.error(f"Failed to save positions: {e}")

def load_positions():
    global active_positions
    try:
        if os.path.exists("positions.json"):
            with open("positions.json", "r") as f:
                active_positions = json.load(f)
            logger.info(f"Restored {len(active_positions)} positions from disk")
    except Exception as e:
        logger.error(f"Position restore failed: {e}")

load_positions()

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM & HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def send_telegram_message(message, parse_mode='HTML'):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    try:
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def safe_float(value, default=0.0):
    try:
        if value is None or (isinstance(value, str) and ("{" in str(value) or "}" in str(value))):
            return default
        return float(value)
    except:
        return default

def format_buy_alert(data):
    symbol = data.get('symbol', 'N/A')
    price = safe_float(data.get('price'))
    sl = safe_float(data.get('sl'))
    tp = safe_float(data.get('tp'))
    qty = safe_float(data.get('qty'))
    risk = safe_float(data.get('risk'))
    rr = safe_float(data.get('rr'), 1)

    if sl == 0 and risk > 0: sl = price - risk
    if tp == 0 and risk > 0: tp = price + (risk * rr)

    confluence = data.get('confluence', 0)
    regime = data.get('regime', 'N/A')
    killzone = data.get('killzone', 'N/A')

    risk_amount = abs(price - sl)
    reward_amount = abs(tp - price)

    message = f"""
🚨 <b>NEW BUY SIGNAL</b> 🚨
━━━━━━━━━━━━━━━━━━━━━
📊 <b>{symbol}</b>
💰 <b>Entry:</b> ₹{price:.2f}
🔻 <b>Stop Loss:</b> ₹{sl:.2f} (-{risk_amount:.2f})
🔺 <b>Take Profit:</b> ₹{tp:.2f} (+{reward_amount:.2f})

💼 <b>Position Details:</b>
• Quantity: {qty:.2f}
• Risk Amount: ₹{risk:.2f}
• Risk-Reward: 1:{rr:.2f}

🎯 <b>Analysis:</b>
• Market Regime: {regime}
• Confluence Score: {confluence}/15
• Kill Zone: {killzone}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

✅ <b>BUY NOW at ₹{price:.2f}</b>
━━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()

def format_sell_alert(data):
    symbol = data.get('symbol', 'N/A')
    price = safe_float(data.get('price'))
    sl = safe_float(data.get('sl'))
    tp = safe_float(data.get('tp'))
    qty = safe_float(data.get('qty'))
    risk = safe_float(data.get('risk'))
    rr = safe_float(data.get('rr'), 1)

    if sl == 0 and risk > 0: sl = price + risk
    if tp == 0 and risk > 0: tp = price - (risk * rr)

    confluence = data.get('confluence', 0)
    regime = data.get('regime', 'N/A')
    killzone = data.get('killzone', 'N/A')

    risk_amount = abs(sl - price)
    reward_amount = abs(price - tp)

    message = f"""
⚠️ <b>NEW SELL SIGNAL</b> ⚠️
━━━━━━━━━━━━━━━━━━━━━
📊 <b>{symbol}</b>
💰 <b>Entry:</b> ₹{price:.2f}
🔺 <b>Stop Loss:</b> ₹{sl:.2f} (+{risk_amount:.2f})
🔻 <b>Take Profit:</b> ₹{tp:.2f} (-{reward_amount:.2f})

💼 <b>Position Details:</b>
• Quantity: {qty:.2f}
• Risk Amount: ₹{risk:.2f}
• Risk-Reward: 1:{rr:.2f}

🎯 <b>Analysis:</b>
• Market Regime: {regime}
• Confluence Score: {confluence}/15
• Kill Zone: {killzone}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

❌ <b>SELL NOW at ₹{price:.2f}</b>
━━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()

# ═══════════════════════════════════════════════════════════════════════════════
# UPSTOX TOKEN AUTO GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
def generate_access_token(auth_code):
    global access_token, token_generated_at
    url = "https://api.upstox.com/v2/login/authorization/token"
    data = {
        'code': auth_code,
        'client_id': UPSTOX_API_KEY,
        'client_secret': UPSTOX_API_SECRET,
        'redirect_uri': UPSTOX_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=data, headers=headers)
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        token_generated_at = datetime.now()
        logger.info("Upstox Access Token Generated Successfully!")
        send_telegram_message("✅ <b>Upstox Token Auto-Generated!</b>\nBot अब live trading के लिए ready है।")
        return True
    else:
        logger.error(f"Token generation failed: {response.text}")
        return False

def is_token_valid():
    if not access_token or not token_generated_at:
        return False
    hours_elapsed = (datetime.now() - token_generated_at).total_seconds() / 3600
    return hours_elapsed < 20

def get_token():
    return access_token if is_token_valid() else None

# ═══════════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
def place_order(order_data, label="Order"):
    token = get_token()
    if not token:
        logger.error("Cannot place order: Token missing")
        return {"success": False, "error": "Token missing"}

    url = "https://api.upstox.com/v2/order/place"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    response = requests.post(url, headers=headers, json=order_data, timeout=10)
    result = response.json()
    order_id = result.get('data', {}).get('order_id')
    success = response.status_code == 200 and result.get('status') == 'success'
    
    log_msg = f"{label} {'SUCCESS' if success else 'FAILED'} | ID: {order_id} | Symbol: {order_data.get('trading_symbol')}"
    logger.info(log_msg)
    if success and TELEGRAM_TOKEN:
        send_telegram_message(f"✅ {label}: {order_data.get('trading_symbol')} | Qty: {order_data.get('quantity')} | ID: {order_id}")
    
    return {
        "success": success,
        "order_id": order_id,
        "raw": result,
        "timestamp": time.time()
    }

def cancel_order(order_id):
    if not order_id or not get_token():
        return
    try:
        url = f"https://api.upstox.com/v2/order/cancel?order_id={order_id}"
        headers = {'Authorization': f'Bearer {get_token()}'}
        requests.delete(url, headers=headers, timeout=10)
        logger.info(f"Cancelled order: {order_id}")
    except Exception as e:
        logger.error(f"Cancel failed {order_id}: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# INSTRUMENT KEY LOADER
# ═══════════════════════════════════════════════════════════════════════════════
instruments_dict = {}

def load_instruments():
    global instruments_dict
    try:
        url = "https://assets.upstox.com/market-quote/instruments/exchange/bod.json"
        response = requests.get(url, timeout=10)
        data = response.json()
        for key, info in data.items():
            if info.get('segment') == 'NSE_EQ':
                instruments_dict[info['trading_symbol'].upper()] = key
        logger.info(f"Loaded {len(instruments_dict)} NSE instruments")
    except Exception as e:
        logger.error(f"Instruments load failed: {e}")

load_instruments()

def get_instrument_key(symbol):
    return instruments_dict.get(symbol.upper())

# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK HANDLER - FULL LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/webhook', methods=['POST'])
def webhook():
    global active_positions
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No data'}), 400

        action = data.get('action', '').upper()
        symbol_raw = data.get('symbol', '')
        symbol = symbol_raw.replace("-EQ", "").replace("NSE:", "").strip().upper()
        qty = max(1, int(round(safe_float(data.get('qty', 1)))))
        sl_price = safe_float(data.get('sl'))
        tp_price = safe_float(data.get('tp'))
        partial_tp_price = safe_float(data.get('partial_tp'))

        if action not in ["BUY", "SELL"]:
            return jsonify({'error': 'Invalid action'}), 400

        instrument_key = get_instrument_key(symbol)
        if not instrument_key:
            return jsonify({'error': f'Symbol {symbol} not found in NSE_EQ'}), 400

        opposite_action = "SELL" if action == "BUY" else "BUY"

        # 🔁 Reversal: Square off existing
        if symbol in active_positions:
            logger.info(f"🔁 Reversal: squaring off {symbol}")
            pos = active_positions[symbol]
            for oid in [pos.get('sl_order_id'), pos.get('tp_order_id'), pos.get('partial_order_id')]:
                cancel_order(oid)
            exit_order = {
                "quantity": pos['filled_qty'],
                "product": "I",
                "validity": "DAY",
                "price": 0,
                "instrument_token": instrument_key,
                "order_type": "MARKET",
                "transaction_type": opposite_action,
                "disclosed_quantity": 0,
                "trigger_price": 0,
                "is_amo": False
            }
            place_order(exit_order, "REVERSAL EXIT")
            del active_positions[symbol]

        # 📤 ENTRY
        entry_order_data = {
            "quantity": qty,
            "product": "I",
            "validity": "DAY",
            "price": 0,
            "instrument_token": instrument_key,
            "order_type": "MARKET",
            "transaction_type": action,
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False
        }
        entry_res = place_order(entry_order_data, "ENTRY")
        if not entry_res["success"]:
            return jsonify({'error': 'Entry order failed'}), 500

        position_state = {
            "symbol": symbol,
            "action": action,
            "qty_requested": qty,
            "filled_qty": qty,
            "entry_order_id": entry_res["order_id"],
            "entry_order_data": entry_order_data,
            "sl_order_id": None,
            "tp_order_id": None,
            "partial_order_id": None,
            "sl_order_data": None,
            "tp_order_data": None,
            "partial_order_data": None,
            "created_at": time.time()
        }

        # 📈 Partial TP (50%)
        if partial_tp_price and qty >= 2:
            partial_qty = qty // 2
            partial_order_data = {
                "quantity": partial_qty,
                "product": "I",
                "validity": "DAY",
                "price": round(partial_tp_price, 2),
                "instrument_token": instrument_key,
                "order_type": "LIMIT",
                "transaction_type": opposite_action,
                "disclosed_quantity": 0,
                "trigger_price": 0,
                "is_amo": False
            }
            partial_res = place_order(partial_order_data, "PARTIAL TP")
            if partial_res["success"]:
                position_state["partial_order_id"] = partial_res["order_id"]
                position_state["partial_order_data"] = partial_order_data

        # 📉 Full TP
        if tp_price:
            full_qty = qty - (qty // 2 if partial_tp_price else 0)
            if full_qty > 0:
                tp_order_data = {
                    "quantity": full_qty,
                    "product": "I",
                    "validity": "DAY",
                    "price": round(tp_price, 2),
                    "instrument_token": instrument_key,
                    "order_type": "LIMIT",
                    "transaction_type": opposite_action,
                    "disclosed_quantity": 0,
                    "trigger_price": 0,
                    "is_amo": False
                }
                tp_res = place_order(tp_order_data, "FULL TP")
                if tp_res["success"]:
                    position_state["tp_order_id"] = tp_res["order_id"]
                    position_state["tp_order_data"] = tp_order_data

        # 🛑 SL (SL-M)
        if sl_price:
            sl_order_data = {
                "quantity": qty,
                "product": "I",
                "validity": "DAY",
                "price": 0,
                "instrument_token": instrument_key,
                "order_type": "SL-M",
                "transaction_type": opposite_action,
                "disclosed_quantity": 0,
                "trigger_price": round(sl_price, 2),
                "is_amo": False
            }
            sl_res = place_order(sl_order_data, "STOP LOSS")
            if sl_res["success"]:
                position_state["sl_order_id"] = sl_res["order_id"]
                position_state["sl_order_data"] = sl_order_data

        active_positions[symbol] = position_state
        save_positions()
        logger.info(f"Position opened: {symbol} | Active: {list(active_positions.keys())}")

        # Telegram Alert
        if action == "BUY":
            message = format_buy_alert(data)
        else:
            message = format_sell_alert(data)
        send_telegram_message(message)

        return jsonify({"status": "Processed", "symbol": symbol}), 200

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - AUTH, TEST, STATS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    token_status = "✅ Active" if is_token_valid() else "❌ Expired/Missing"
    return jsonify({
        'bot': 'ICT Pro Bot V7.4',
        'status': 'active',
        'trades_today': len([t for t in active_positions]),
        'upstox_token': token_status,
        'login_url': f"{request.url_root}login"
    })

@app.route('/login')
def login():
    if not UPSTOX_API_KEY or not UPSTOX_API_SECRET:
        return "Error: Upstox credentials missing!", 500
    auth_url = (
        "https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={UPSTOX_API_KEY}&redirect_uri={UPSTOX_REDIRECT_URI}"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "<h2>❌ Error: No authorization code</h2>", 400
    if generate_access_token(code):
        return """
        <h1 style="color:green;">✅ SUCCESS!</h1>
        <h2>Upstox Token Generated!</h2>
        <p>Bot अब live trading के लिए तैयार है।</p>
        <p><a href="/">← Back</a></p>
        """
    else:
        return "<h2 style='color:red;'>❌ Token Generation Failed</h2>", 500

@app.route('/test', methods=['GET'])
def test_alert():
    test_data = {
        'action': 'BUY', 'symbol': 'RELIANCE-EQ', 'qty': 1,
        'sl': 2950.00, 'tp': 3100.00, 'partial_tp': 3025.00
    }
    message = format_buy_alert(test_data)
    send_telegram_message(message)
    return jsonify({'status': 'Test alert sent'})

@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        'active_positions': len(active_positions),
        'positions': list(active_positions.keys()),
        'upstox_token_valid': is_token_valid()
    })

# ═══════════════════════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════
def graceful_shutdown(signum, frame):
    logger.info("🛑 Shutting down... Cancelling all active orders")
    for symbol, pos in active_positions.items():
        for oid in [pos.get('sl_order_id'), pos.get('tp_order_id'), pos.get('partial_order_id')]:
            cancel_order(oid)
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

# ═══════════════════════════════════════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    startup_msg = f"""
🤖 <b>ICT PRO BOT V7.4 STARTED</b> 🤖
━━━━━━━━━━━━━━━━━━━━━
✅ Status: Running
📅 {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
🔑 Token: {'✅ Valid' if is_token_valid() else '❌ Login Required → /login'}
📈 Auto Trading: ENABLED (SL/TP/Partial/Reversal)
━━━━━━━━━━━━━━━━━━━━━
"""
    send_telegram_message(startup_msg)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
