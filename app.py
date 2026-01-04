#!/usr/bin/env python3
"""
ICT PRO BOT V7.4 - PRODUCTION READY
✅ Order Fill Verification | ✅ Market Hours Check | ✅ Partial Fill Handling
✅ SL Quantity Adjustment | ✅ Token Expiry Monitor | ✅ Error Recovery
✅ Position Reconciliation | ✅ Emergency Exit | ✅ Complete Lifecycle Management
"""

from flask import Flask, request, jsonify, redirect
import requests
import json
from datetime import datetime, time as dt_time
import logging
import os
from threading import Thread
import time
import signal
import sys
import pytz

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else ""

# Upstox Credentials
UPSTOX_API_KEY = os.environ.get("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.environ.get("UPSTOX_API_SECRET")
UPSTOX_REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI", "https://your-render-url.onrender.com/callback")

# Trading Configuration
MAX_ORDER_RETRIES = 3
ORDER_FILL_TIMEOUT = 30  # seconds
POSITION_RECONCILE_INTERVAL = 300  # 5 minutes

# Global State
access_token = None
token_generated_at = None
active_positions = {}  # symbol → full state dict
instruments_dict = {}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ict-pro-bot-v7-4-production'

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/trade_log_{datetime.now().strftime('%Y%m%d')}.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
def save_positions():
    """Save positions to disk for crash recovery"""
    try:
        with open("positions.json", "w") as f:
            json.dump(active_positions, f, indent=2)
        logger.info(f"✅ Positions saved: {list(active_positions.keys())}")
    except Exception as e:
        logger.error(f"❌ Position save failed: {e}")

def load_positions():
    """Load positions from disk on startup"""
    global active_positions
    try:
        if os.path.exists("positions.json"):
            with open("positions.json", "r") as f:
                active_positions = json.load(f)
            logger.info(f"✅ Restored {len(active_positions)} positions from disk")
    except Exception as e:
        logger.error(f"❌ Position restore failed: {e}")
        active_positions = {}

load_positions()

# ═══════════════════════════════════════════════════════════════════════════════
# MARKET HOURS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
def is_market_open():
    """Check if NSE market is open (9:15 AM - 3:30 PM IST, Mon-Fri)"""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            logger.warning("⚠️ Market closed: Weekend")
            return False
        
        # Time check
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)
        current_time = now.time()
        
        if current_time < market_open:
            logger.warning(f"⚠️ Market not yet open (opens at 9:15 AM IST)")
            return False
        
        if current_time > market_close:
            logger.warning(f"⚠️ Market closed (closed at 3:30 PM IST)")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Market hours check failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════
def send_telegram_message(message, parse_mode='HTML'):
    """Send Telegram notification"""
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
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        if value is None or (isinstance(value, str) and ("{" in str(value) or "}" in str(value))):
            return default
        return float(value)
    except:
        return default

def format_buy_alert(data):
    """Format BUY signal alert message"""
    symbol = data.get('symbol', 'N/A')
    price = safe_float(data.get('price'))
    sl = safe_float(data.get('sl'))
    tp = safe_float(data.get('tp'))
    partial_tp = safe_float(data.get('partial_tp'))
    qty = safe_float(data.get('qty'))
    risk = safe_float(data.get('risk'))
    rr = safe_float(data.get('rr'), 1)
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
🎯 <b>Partial TP (50%):</b> ₹{partial_tp:.2f}
🔺 <b>Full TP:</b> ₹{tp:.2f} (+{reward_amount:.2f})

💼 <b>Position Details:</b>
• Quantity: {qty:.0f}
• Risk Amount: ₹{risk:.2f}
• Risk-Reward: 1:{rr:.2f}

🎯 <b>Analysis:</b>
• Market Regime: {regime}
• Confluence Score: {confluence}/15
• Kill Zone: {killzone}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

✅ <b>EXECUTING BUY ORDER...</b>
━━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()

def format_sell_alert(data):
    """Format SELL signal alert message"""
    symbol = data.get('symbol', 'N/A')
    price = safe_float(data.get('price'))
    sl = safe_float(data.get('sl'))
    tp = safe_float(data.get('tp'))
    partial_tp = safe_float(data.get('partial_tp'))
    qty = safe_float(data.get('qty'))
    risk = safe_float(data.get('risk'))
    rr = safe_float(data.get('rr'), 1)
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
🎯 <b>Partial TP (50%):</b> ₹{partial_tp:.2f}
🔻 <b>Full TP:</b> ₹{tp:.2f} (-{reward_amount:.2f})

💼 <b>Position Details:</b>
• Quantity: {qty:.0f}
• Risk Amount: ₹{risk:.2f}
• Risk-Reward: 1:{rr:.2f}

🎯 <b>Analysis:</b>
• Market Regime: {regime}
• Confluence Score: {confluence}/15
• Kill Zone: {killzone}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

❌ <b>EXECUTING SELL ORDER...</b>
━━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()

# ═══════════════════════════════════════════════════════════════════════════════
# UPSTOX TOKEN MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
def generate_access_token(auth_code):
    """Generate Upstox access token from authorization code"""
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
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data['access_token']
            token_generated_at = datetime.now()
            logger.info("✅ Upstox Access Token Generated Successfully!")
            send_telegram_message("✅ <b>Upstox Token Auto-Generated!</b>\nBot अब live trading के लिए ready है।")
            return True
        else:
            logger.error(f"❌ Token generation failed: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Token generation error: {e}")
        return False

def is_token_valid():
    """Check if current token is still valid (< 20 hours old)"""
    if not access_token or not token_generated_at:
        return False
    hours_elapsed = (datetime.now() - token_generated_at).total_seconds() / 3600
    return hours_elapsed < 20

def get_token():
    """Get valid token or None"""
    return access_token if is_token_valid() else None

def token_expiry_monitor():
    """Background thread to monitor token expiry"""
    while True:
        try:
            if token_generated_at:
                hours_left = 20 - ((datetime.now() - token_generated_at).total_seconds() / 3600)
                if hours_left < 1 and hours_left > 0:
                    msg = f"⚠️ <b>TOKEN EXPIRING SOON!</b>\n\nToken will expire in {int(hours_left * 60)} minutes.\n\nLogin at: {UPSTOX_REDIRECT_URI.replace('/callback', '/login')}"
                    send_telegram_message(msg)
                    logger.warning(f"⚠️ Token expiring in {hours_left:.2f} hours")
            time.sleep(1800)  # Check every 30 minutes
        except Exception as e:
            logger.error(f"Token monitor error: {e}")
            time.sleep(1800)

# Start token monitor thread
Thread(target=token_expiry_monitor, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════════════════
# INSTRUMENT KEY LOADER
# ═══════════════════════════════════════════════════════════════════════════════
def load_instruments():
    """Load NSE instrument keys from Upstox"""
    global instruments_dict
    try:
        url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
        response = requests.get(url, timeout=30)
        
        import gzip
        import io
        data = json.loads(gzip.decompress(response.content))
        
        for key, info in data.items():
            if info.get('instrument_type') == 'EQUITY' and info.get('exchange') == 'NSE':
                trading_symbol = info['trading_symbol'].upper()
                instruments_dict[trading_symbol] = key
                # Also store without -EQ suffix
                if trading_symbol.endswith('-EQ'):
                    base_symbol = trading_symbol.replace('-EQ', '')
                    instruments_dict[base_symbol] = key
        
        logger.info(f"✅ Loaded {len(instruments_dict)} NSE instruments")
    except Exception as e:
        logger.error(f"❌ Instruments load failed: {e}")

load_instruments()

def get_instrument_key(symbol):
    """Get Upstox instrument key for symbol"""
    symbol_clean = symbol.upper().replace("NSE:", "").strip()
    
    # Try exact match first
    if symbol_clean in instruments_dict:
        return instruments_dict[symbol_clean]
    
    # Try with -EQ suffix
    if not symbol_clean.endswith('-EQ'):
        eq_symbol = f"{symbol_clean}-EQ"
        if eq_symbol in instruments_dict:
            return instruments_dict[eq_symbol]
    
    logger.error(f"❌ Instrument not found: {symbol_clean}")
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT WITH VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
def get_order_status(order_id):
    """Get current status of an order"""
    token = get_token()
    if not token or not order_id:
        return None
    
    try:
        url = f"https://api.upstox.com/v2/order/details?order_id={order_id}"
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('status')
        return None
    except Exception as e:
        logger.error(f"Order status check failed {order_id}: {e}")
        return None

def verify_order_fill(order_id, timeout=ORDER_FILL_TIMEOUT):
    """Wait and verify if order is filled"""
    if not order_id:
        return False, 0
    
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        status = get_order_status(order_id)
        
        if status == "complete":
            logger.info(f"✅ Order {order_id} FILLED")
            return True, get_filled_quantity(order_id)
        elif status in ["rejected", "cancelled"]:
            logger.error(f"❌ Order {order_id} {status.upper()}")
            return False, 0
        
        time.sleep(2)
    
    logger.warning(f"⚠️ Order {order_id} fill timeout")
    return False, 0

def get_filled_quantity(order_id):
    """Get actual filled quantity from order"""
    token = get_token()
    if not token or not order_id:
        return 0
    
    try:
        url = f"https://api.upstox.com/v2/order/details?order_id={order_id}"
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            order_data = data.get('data', {})
            return int(order_data.get('filled_quantity', 0))
        return 0
    except Exception as e:
        logger.error(f"Get filled qty failed {order_id}: {e}")
        return 0

def place_order(order_data, label="Order", retry_count=0):
    """Place order with retry logic"""
    token = get_token()
    if not token:
        logger.error("❌ Cannot place order: Token missing")
        return {"success": False, "error": "Token missing", "order_id": None}

    url = "https://api.upstox.com/v2/order/place"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, json=order_data, timeout=10)
        result = response.json()
        order_id = result.get('data', {}).get('order_id')
        success = response.status_code == 200 and result.get('status') == 'success'
        
        if success:
            logger.info(f"✅ {label} SUCCESS | ID: {order_id} | Symbol: {order_data.get('instrument_token')}")
            if TELEGRAM_TOKEN:
                qty = order_data.get('quantity')
                trans_type = order_data.get('transaction_type')
                send_telegram_message(f"✅ {label}: {trans_type} {qty} | ID: {order_id}")
        else:
            logger.error(f"❌ {label} FAILED | Response: {result}")
            if retry_count < MAX_ORDER_RETRIES:
                logger.info(f"🔄 Retrying... ({retry_count + 1}/{MAX_ORDER_RETRIES})")
                time.sleep(2)
                return place_order(order_data, label, retry_count + 1)
        
        return {
            "success": success,
            "order_id": order_id,
            "raw": result,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"❌ {label} exception: {e}")
        if retry_count < MAX_ORDER_RETRIES:
            logger.info(f"🔄 Retrying... ({retry_count + 1}/{MAX_ORDER_RETRIES})")
            time.sleep(2)
            return place_order(order_data, label, retry_count + 1)
        return {"success": False, "error": str(e), "order_id": None}

def cancel_order(order_id):
    """Cancel an order"""
    if not order_id or not get_token():
        return False
    try:
        url = f"https://api.upstox.com/v2/order/cancel?order_id={order_id}"
        headers = {'Authorization': f'Bearer {get_token()}'}
        response = requests.delete(url, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Cancelled order: {order_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Cancel failed {order_id}: {e}")
        return False

def emergency_exit_position(symbol, quantity, action):
    """Emergency market exit for unprotected positions"""
    logger.critical(f"🚨 EMERGENCY EXIT: {symbol} | Qty: {quantity}")
    
    instrument_key = get_instrument_key(symbol)
    if not instrument_key:
        logger.error(f"❌ Emergency exit failed: Symbol not found")
        return False
    
    exit_action = "SELL" if action == "BUY" else "BUY"
    exit_order = {
        "quantity": quantity,
        "product": "I",
        "validity": "DAY",
        "price": 0,
        "instrument_token": instrument_key,
        "order_type": "MARKET",
        "transaction_type": exit_action,
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False
    }
    
    result = place_order(exit_order, "EMERGENCY EXIT")
    
    if result["success"]:
        send_telegram_message(f"🚨 <b>EMERGENCY EXIT EXECUTED</b>\n\nSymbol: {symbol}\nQuantity: {quantity}\nReason: SL placement failed")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK HANDLER - PRODUCTION GRADE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/webhook', methods=['POST'])
def webhook():
    global active_positions
    
    try:
        # ✅ 1. Parse webhook data
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'No data'}), 400

        action = data.get('action', '').upper()
        symbol_raw = data.get('symbol', '')
        symbol = symbol_raw.replace("-EQ", "").replace("NSE:", "").strip().upper()
        qty_requested = max(1, int(round(safe_float(data.get('qty', 1)))))
        sl_price = safe_float(data.get('sl'))
        tp_price = safe_float(data.get('tp'))
        partial_tp_price = safe_float(data.get('partial_tp'))

        # ✅ 2. Validate action
        if action not in ["BUY", "SELL"]:
            return jsonify({'error': 'Invalid action'}), 400

        # ✅ 3. Market hours check
        if not is_market_open():
            logger.warning(f"⚠️ Order rejected: Market closed")
            send_telegram_message(f"⚠️ <b>Order Rejected</b>\n\nMarket is closed. Signal: {action} {symbol}")
            return jsonify({'error': 'Market closed'}), 400

        # ✅ 4. Get instrument key
        instrument_key = get_instrument_key(symbol)
        if not instrument_key:
            return jsonify({'error': f'Symbol {symbol} not found in NSE_EQ'}), 400

        opposite_action = "SELL" if action == "BUY" else "BUY"

        # ✅ 5. Handle reversal (square off existing position)
        if symbol in active_positions:
            logger.info(f"🔁 REVERSAL: Squaring off {symbol}")
            pos = active_positions[symbol]
            
            # Cancel all pending orders
            for oid in [pos.get('sl_order_id'), pos.get('tp_order_id'), pos.get('partial_order_id')]:
                if oid:
                    cancel_order(oid)
            
            # Market exit
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
            save_positions()

        # ✅ 6. Send entry alert to Telegram
        if action == "BUY":
            message = format_buy_alert(data)
        else:
            message = format_sell_alert(data)
        send_telegram_message(message)

        # ✅ 7. Place ENTRY order
        entry_order_data = {
            "quantity": qty_requested,
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
        
        entry_res = place_order(entry_order_data, "ENTRY ORDER")
        if not entry_res["success"]:
            send_telegram_message(f"❌ <b>ENTRY FAILED</b>\n\nSymbol: {symbol}\nAction: {action}")
            return jsonify({'error': 'Entry order failed'}), 500

        # ✅ 8. Verify entry fill
        is_filled, filled_qty = verify_order_fill(entry_res["order_id"])
        if not is_filled or filled_qty == 0:
            logger.error(f"❌ Entry not filled: {symbol}")
            send_telegram_message(f"❌ <b>ENTRY NOT FILLED</b>\n\nSymbol: {symbol}\nOrder ID: {entry_res['order_id']}")
            return jsonify({'error': 'Entry not filled'}), 500

        logger.info(f"✅ Entry filled: {symbol} | Qty: {filled_qty}")

        # ✅ 9. Initialize position state
        position_state = {
            "symbol": symbol,
            "action": action,
            "qty_requested": qty_requested,
            "filled_qty": filled_qty,
            "entry_order_id": entry_res["order_id"],
            "entry_order_data": entry_order_data,
            "sl_order_id": None,
            "tp_order_id": None,
            "partial_order_id": None,
            "sl_order_data": None,
            "tp_order_data": None,
            "partial_order_data": None,
            "partial_filled": False,
            "created_at": time.time()
        }

        # ✅ 10. Place PARTIAL TP (50% at RR 1:2)
        if partial_tp_price and filled_qty >= 2:
            partial_qty = filled_qty // 2
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
            partial_res = place_order(partial_order_data, "PARTIAL TP (50%)")
            if partial_res["success"]:
                position_state["partial_order_id"] = partial_res["order_id"]
                position_state["partial_order_data"] = partial_order_data

        # ✅ 11. Place FULL TP (remaining qty)
        if tp_price:
            remaining_qty = filled_qty - (filled_qty // 2 if partial_tp_price and filled_qty >= 2 else 0)
            if remaining_qty > 0:
                tp_order_data = {
                    "quantity": remaining_qty,
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

        # ✅ 12. Place STOP LOSS (CRITICAL - Full qty initially)
        if sl_price:
            sl_order_data = {
                "quantity": filled_qty,  # Full quantity
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
            else:
                # 🚨 CRITICAL: SL placement failed - Emergency exit
                logger.critical(f"🚨 SL PLACEMENT FAILED: {symbol}")
                emergency_exit_position(symbol, filled_qty, action)
                send_telegram_message(f"🚨 <b>CRITICAL ERROR</b>\n\nSL placement failed for {symbol}\nEmergency market exit executed!")
                return jsonify({'error': 'SL placement failed - emergency exit'}), 500

        # ✅ 13. Save position
        active_positions[symbol] = position_state
        save_positions()
        
        logger.info(f"✅ Position opened: {symbol} | Filled: {filled_qty}/{qty_requested}")
        
        # ✅ 14. Send success notification
        success_msg = f"""
✅ <b>POSITION OPENED</b>
━━━━━━━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
🎯 Action: {action}
📈 Filled Qty: {filled_qty}
🔻 SL Order: {'✅ Placed' if position_state['sl_order_id'] else '❌ Failed'}
🔺 TP Order: {'✅ Placed' if position_state['tp_order_id'] else '⚠️ Not Placed'}
🎯 Partial TP: {'✅ Placed' if position_state['partial_order_id'] else '⚠️ Not Placed'}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
"""
        send_telegram_message(success_msg)

        return jsonify({
            "status": "success",
            "symbol": symbol,
            "action": action,
            "filled_qty": filled_qty,
            "orders_placed": {
                "entry": entry_res["order_id"],
                "sl": position_state["sl_order_id"],
                "tp": position_state["tp_order_id"],
                "partial_tp": position_state["partial_order_id"]
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        send_telegram_message(f"❌ <b>WEBHOOK ERROR</b>\n\n{str(e)}")
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# POSITION MONITORING & PARTIAL FILL HANDLING
# ═══════════════════════════════════════════════════════════════════════════════
def monitor_partial_fills():
    """Background thread to monitor partial TP fills and adjust SL quantity"""
    while True:
        try:
            for symbol, pos in list(active_positions.items()):
                # Check if partial TP order exists and is not yet marked as filled
                if pos.get('partial_order_id') and not pos.get('partial_filled'):
                    status = get_order_status(pos['partial_order_id'])
                    
                    if status == "complete":
                        logger.info(f"✅ Partial TP filled: {symbol}")
                        pos['partial_filled'] = True
                        
                        # ✅ CRITICAL: Adjust SL quantity
                        partial_qty = pos['partial_order_data']['quantity']
                        remaining_qty = pos['filled_qty'] - partial_qty
                        
                        # Cancel old SL and place new SL with reduced quantity
                        if pos.get('sl_order_id'):
                            cancel_order(pos['sl_order_id'])
                            
                            # Get instrument key
                            instrument_key = get_instrument_key(symbol)
                            if instrument_key:
                                opposite_action = "SELL" if pos['action'] == "BUY" else "BUY"
                                
                                new_sl_order = {
                                    "quantity": remaining_qty,  # ✅ Adjusted quantity
                                    "product": "I",
                                    "validity": "DAY",
                                    "price": 0,
                                    "instrument_token": instrument_key,
                                    "order_type": "SL-M",
                                    "transaction_type": opposite_action,
                                    "disclosed_quantity": 0,
                                    "trigger_price": pos['sl_order_data']['trigger_price'],
                                    "is_amo": False
                                }
                                
                                sl_res = place_order(new_sl_order, "ADJUSTED SL")
                                if sl_res["success"]:
                                    pos['sl_order_id'] = sl_res["order_id"]
                                    pos['sl_order_data'] = new_sl_order
                                    logger.info(f"✅ SL adjusted: {symbol} | New qty: {remaining_qty}")
                                    
                                    send_telegram_message(f"""
✅ <b>PARTIAL PROFIT TAKEN</b>
━━━━━━━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
💰 Qty Exited: {partial_qty}
📈 Remaining: {remaining_qty}
🔄 SL Adjusted: {remaining_qty}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
""")
                                else:
                                    logger.critical(f"🚨 SL adjustment failed: {symbol}")
                                    emergency_exit_position(symbol, remaining_qty, pos['action'])
                        
                        save_positions()
                
                # Check if full TP is hit
                if pos.get('tp_order_id'):
                    status = get_order_status(pos['tp_order_id'])
                    if status == "complete":
                        logger.info(f"✅ Full TP hit: {symbol}")
                        # Position should be fully closed now
                        if pos.get('sl_order_id'):
                            cancel_order(pos['sl_order_id'])
                        del active_positions[symbol]
                        save_positions()
                        
                        send_telegram_message(f"""
🎯 <b>TAKE PROFIT HIT</b>
━━━━━━━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
✅ Position fully closed
💰 Target achieved!

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
""")
                
                # Check if SL is hit
                if pos.get('sl_order_id'):
                    status = get_order_status(pos['sl_order_id'])
                    if status == "complete":
                        logger.info(f"🛑 Stop Loss hit: {symbol}")
                        # Cancel any remaining orders
                        if pos.get('tp_order_id'):
                            cancel_order(pos['tp_order_id'])
                        if pos.get('partial_order_id'):
                            cancel_order(pos['partial_order_id'])
                        del active_positions[symbol]
                        save_positions()
                        
                        send_telegram_message(f"""
🛑 <b>STOP LOSS HIT</b>
━━━━━━━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
❌ Position closed at loss
🔒 Risk protected

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
""")
            
            time.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            logger.error(f"❌ Monitor error: {e}")
            time.sleep(10)

# Start position monitor thread
Thread(target=monitor_partial_fills, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════════════════
# POSITION RECONCILIATION (Safety Check)
# ═══════════════════════════════════════════════════════════════════════════════
def reconcile_positions():
    """Periodically check actual positions vs tracked positions"""
    while True:
        try:
            time.sleep(POSITION_RECONCILE_INTERVAL)
            
            if not get_token():
                continue
            
            # Get actual positions from Upstox
            url = "https://api.upstox.com/v2/portfolio/short-term-positions"
            headers = {'Authorization': f'Bearer {get_token()}'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                continue
            
            data = response.json()
            actual_positions = {}
            
            for pos in data.get('data', []):
                symbol = pos.get('trading_symbol', '').replace('-EQ', '').upper()
                qty = int(pos.get('quantity', 0))
                if qty != 0:
                    actual_positions[symbol] = qty
            
            # Compare with tracked positions
            tracked_symbols = set(active_positions.keys())
            actual_symbols = set(actual_positions.keys())
            
            # Positions that exist in tracking but not in actual
            ghost_positions = tracked_symbols - actual_symbols
            if ghost_positions:
                logger.warning(f"⚠️ Ghost positions detected: {ghost_positions}")
                for symbol in ghost_positions:
                    del active_positions[symbol]
                    send_telegram_message(f"⚠️ <b>Ghost position removed</b>\n\nSymbol: {symbol}\nReason: Not found in actual positions")
                save_positions()
            
            # Positions that exist in actual but not in tracking
            untracked_positions = actual_symbols - tracked_symbols
            if untracked_positions:
                logger.warning(f"⚠️ Untracked positions: {untracked_positions}")
                send_telegram_message(f"⚠️ <b>Untracked positions detected</b>\n\nSymbols: {', '.join(untracked_positions)}\n\nThese may be manual trades.")
            
        except Exception as e:
            logger.error(f"❌ Reconciliation error: {e}")

# Start reconciliation thread
Thread(target=reconcile_positions, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - AUTH, TEST, STATS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    """Home endpoint with bot status"""
    token_status = "✅ Active" if is_token_valid() else "❌ Expired/Missing"
    market_status = "✅ Open" if is_market_open() else "❌ Closed"
    
    return jsonify({
        'bot': 'ICT Pro Bot V7.4 - Production Ready',
        'status': 'active',
        'upstox_token': token_status,
        'market_status': market_status,
        'active_positions': len(active_positions),
        'positions': list(active_positions.keys()),
        'login_url': f"{request.url_root}login",
        'webhook_url': f"{request.url_root}webhook"
    })

@app.route('/login')
def login():
    """Initiate Upstox OAuth login"""
    if not UPSTOX_API_KEY or not UPSTOX_API_SECRET:
        return "<h2 style='color:red;'>❌ Error: Upstox credentials missing in environment variables!</h2>", 500
    
    auth_url = (
        "https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={UPSTOX_API_KEY}&redirect_uri={UPSTOX_REDIRECT_URI}"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """Handle Upstox OAuth callback"""
    code = request.args.get('code')
    if not code:
        return "<h2 style='color:red;'>❌ Error: No authorization code received</h2>", 400
    
    if generate_access_token(code):
        return f"""
        <html>
        <head><title>Success</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color:green;">✅ SUCCESS!</h1>
            <h2>Upstox Token Generated Successfully!</h2>
            <p style="font-size: 18px;">Bot is now ready for live trading</p>
            <p style="font-size: 16px; color: #666;">Token valid for 20 hours</p>
            <p><a href="/" style="color: blue; text-decoration: none;">← Back to Dashboard</a></p>
        </body>
        </html>
        """
    else:
        return "<h2 style='color:red;'>❌ Token Generation Failed</h2><p>Check logs for details</p>", 500

@app.route('/test', methods=['GET'])
def test_alert():
    """Test webhook with sample data"""
    test_data = {
        'action': 'BUY',
        'symbol': 'RELIANCE-EQ',
        'price': 2980.50,
        'sl': 2950.00,
        'tp': 3100.00,
        'partial_tp': 3040.25,
        'qty': 10,
        'risk': 305.00,
        'rr': 3.93,
        'regime': 'TRENDING',
        'confluence': 12,
        'killzone': 'NSE/BSE Session'
    }
    
    message = format_buy_alert(test_data)
    send_telegram_message(message)
    
    return jsonify({
        'status': 'Test alert sent to Telegram',
        'data': test_data
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get bot statistics"""
    token_hours_left = 0
    if token_generated_at:
        token_hours_left = max(0, 20 - ((datetime.now() - token_generated_at).total_seconds() / 3600))
    
    positions_detail = []
    for symbol, pos in active_positions.items():
        positions_detail.append({
            'symbol': symbol,
            'action': pos['action'],
            'filled_qty': pos['filled_qty'],
            'partial_filled': pos.get('partial_filled', False),
            'created_at': datetime.fromtimestamp(pos['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify({
        'bot_version': 'V7.4 Production',
        'status': 'active',
        'upstox_token_valid': is_token_valid(),
        'token_hours_remaining': round(token_hours_left, 2),
        'market_open': is_market_open(),
        'active_positions_count': len(active_positions),
        'positions': positions_detail,
        'features': {
            'order_fill_verification': True,
            'market_hours_check': True,
            'partial_fill_handling': True,
            'sl_adjustment': True,
            'position_reconciliation': True,
            'emergency_exit': True,
            'token_expiry_monitor': True
        }
    })

@app.route('/positions', methods=['GET'])
def get_positions():
    """Get detailed position information"""
    return jsonify({
        'active_positions': active_positions,
        'count': len(active_positions)
    })

@app.route('/close/<symbol>', methods=['POST'])
def manual_close(symbol):
    """Manually close a position"""
    symbol = symbol.upper().replace('-EQ', '')
    
    if symbol not in active_positions:
        return jsonify({'error': f'Position {symbol} not found'}), 404
    
    pos = active_positions[symbol]
    
    # Cancel all orders
    for oid in [pos.get('sl_order_id'), pos.get('tp_order_id'), pos.get('partial_order_id')]:
        if oid:
            cancel_order(oid)
    
    # Market exit
    instrument_key = get_instrument_key(symbol)
    if not instrument_key:
        return jsonify({'error': 'Instrument key not found'}), 400
    
    opposite_action = "SELL" if pos['action'] == "BUY" else "BUY"
    remaining_qty = pos['filled_qty'] - (pos['partial_order_data']['quantity'] if pos.get('partial_filled') else 0)
    
    exit_order = {
        "quantity": remaining_qty,
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
    
    result = place_order(exit_order, "MANUAL EXIT")
    
    if result["success"]:
        del active_positions[symbol]
        save_positions()
        send_telegram_message(f"✅ <b>Manual Exit</b>\n\nSymbol: {symbol}\nQty: {remaining_qty}")
        return jsonify({'success': True, 'message': f'Position {symbol} closed'})
    else:
        return jsonify({'error': 'Exit order failed'}), 500

@app.route('/close_all', methods=['POST'])
def close_all_positions():
    """Emergency close all positions"""
    closed = []
    failed = []
    
    for symbol, pos in list(active_positions.items()):
        # Cancel all orders
        for oid in [pos.get('sl_order_id'), pos.get('tp_order_id'), pos.get('partial_order_id')]:
            if oid:
                cancel_order(oid)
        
        # Market exit
        instrument_key = get_instrument_key(symbol)
        if instrument_key:
            opposite_action = "SELL" if pos['action'] == "BUY" else "BUY"
            remaining_qty = pos['filled_qty'] - (pos['partial_order_data']['quantity'] if pos.get('partial_filled') else 0)
            
            exit_order = {
                "quantity": remaining_qty,
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
            
            result = place_order(exit_order, f"EMERGENCY EXIT {symbol}")
            if result["success"]:
                closed.append(symbol)
                del active_positions[symbol]
            else:
                failed.append(symbol)
    
    save_positions()
    send_telegram_message(f"🚨 <b>Emergency Close All</b>\n\nClosed: {', '.join(closed)}\nFailed: {', '.join(failed)}")
    
    return jsonify({
        'closed': closed,
        'failed': failed,
        'remaining_positions': len(active_positions)
    })

# ═══════════════════════════════════════════════════════════════════════════════
# GRACEFUL SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════
def graceful_shutdown(signum, frame):
    """Handle shutdown gracefully - cancel all pending orders"""
    logger.info("🛑 Shutting down... Cancelling all pending orders")
    
    for symbol, pos in active_positions.items():
        for oid in [pos.get('sl_order_id'), pos.get('tp_order_id'), pos.get('partial_order_id')]:
            if oid:
                cancel_order(oid)
    
    send_telegram_message("🛑 <b>Bot Shutting Down</b>\n\nAll pending orders cancelled.\nPositions remain open.")
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

# ═══════════════════════════════════════════════════════════════════════════════
# START APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    startup_msg = f"""
🤖 <b>ICT PRO BOT V7.4 STARTED</b> 🤖
━━━━━━━━━━━━━━━━━━━━━
✅ Status: Running
📅 {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
🔑 Token: {'✅ Valid' if is_token_valid() else '❌ Login Required'}
📈 Market: {'✅ Open' if is_market_open() else '❌ Closed'}
🎯 Active Positions: {len(active_positions)}

<b>Features Enabled:</b>
✅ Order Fill Verification
✅ Market Hours Check
✅ Partial Fill Handling
✅ SL Quantity Adjustment
✅ Position Reconciliation
✅ Emergency Exit Protocol
✅ Token Expiry Monitor

━━━━━━━━━━━━━━━━━━━━━
"""
    send_telegram_message(startup_msg)
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
