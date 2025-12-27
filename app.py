#!/usr/bin/env python3
"""
ICT PRO BOT V7.0 - FULL AUTO Upstox Token + Telegram Alerts + AUTO ORDER PLACEMENT
Fully Optimized for Render.com Deployment
"""

from flask import Flask, request, jsonify, redirect
import requests
import json
from datetime import datetime
import logging
import os
from threading import Thread
import time

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Environment Variables (Render.com में सेट करें)
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("8520294976:AAG7cvsDUECK2kbwIzqCCj3yRSeBPeY-4O8")          # ← सही तरीका: key name
CHAT_ID = os.environ.get("7340945498")                        # ← key name
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Upstox Credentials - Render Environment Variables से लोड होंगे
UPSTOX_API_KEY = os.environ.get("f476e97e-a6eb-403d-8456-be18142870f4")          # ← key name
UPSTOX_API_SECRET = os.environ.get("qst633yx7w")    # ← key name
UPSTOX_REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI", "https://advbot-b248.onrender.com/callback")

# Global Access Token Storage
access_token = None
token_generated_at = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ict-pro-bot-v7-2026'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# TRADE TRACKING
# ═══════════════════════════════════════════════════════════════════════════════
class TradeTracker:
    def __init__(self):
        self.trades = []
        self.daily_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'start_time': datetime.now()
        }
    
    def add_trade(self, trade_data):
        self.trades.append({'timestamp': datetime.now().isoformat(), 'data': trade_data})
        self.daily_stats['total_trades'] += 1
        logger.info(f"Trade added: {trade_data.get('symbol')} - {trade_data.get('action')}")

    def update_pnl(self, pnl):
        self.daily_stats['total_pnl'] += pnl
        if pnl > 0:
            self.daily_stats['winning_trades'] += 1
        else:
            self.daily_stats['losing_trades'] += 1

    def get_win_rate(self):
        total = self.daily_stats['total_trades']
        return (self.daily_stats['winning_trades'] / total) * 100 if total > 0 else 0

    def reset_daily_stats(self):
        self.daily_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'start_time': datetime.now()
        }
        logger.info("Daily stats reset")

tracker = TradeTracker()

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM & HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def send_telegram_message(message, parse_mode='HTML'):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("Telegram credentials missing!")
        return False
    try:
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram message sent")
            return True
        else:
            logger.error(f"Telegram error: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Send error: {str(e)}")
        return False

def safe_float(value, default=0.0):
    try:
        if value is None or (isinstance(value, str) and "{{" in value):
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

def format_close_alert(data):
    symbol = data.get('symbol', 'N/A')
    try:
        pnl_pct = float(data.get('pnl_percent', 0))
    except:
        pnl_pct = 0.0
    reason = data.get('reason', 'Target/SL Hit')
    emoji = "✅" if pnl_pct > 0 else "❌"
    status = "PROFIT" if pnl_pct > 0 else "LOSS"

    message = f"""
{emoji} <b>TRADE CLOSED - {status}</b> {emoji}
━━━━━━━━━━━━━━━━━━━━━
📊 <b>{symbol}</b>
💰 <b>P&L:</b> {pnl_pct:+.2f}%
📝 <b>Reason:</b> {reason}

📈 <b>Daily Stats:</b>
• Total Trades: {tracker.daily_stats['total_trades']}
• Win Rate: {tracker.get_win_rate():.1f}%
• Total P&L: ₹{tracker.daily_stats['total_pnl']:+.2f}

⏰ {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━
"""
    return message.strip()

def format_daily_summary():
    win_rate = tracker.get_win_rate()
    message = f"""
📊 <b>DAILY TRADING SUMMARY</b> 📊
━━━━━━━━━━━━━━━━━━━━━
📅 <b>{datetime.now().strftime('%d-%m-%Y')}</b>

✅ <b>Performance:</b>
• Total Trades: {tracker.daily_stats['total_trades']}
• Winning Trades: {tracker.daily_stats['winning_trades']} ✅
• Losing Trades: {tracker.daily_stats['losing_trades']} ❌
• Win Rate: {win_rate:.1f}%

💰 <b>P&L:</b> ₹{tracker.daily_stats['total_pnl']:+.2f}

⏰ <b>Session:</b>
• Started: {tracker.daily_stats['start_time'].strftime('%H:%M:%S')}
• Ended: {datetime.now().strftime('%H:%M:%S')}

🤖 <b>ICT PRO BOT V7.0</b>
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
        send_telegram_message(f"❌ Token generation failed:\n{response.text}")
        return False

def is_token_valid():
    if not access_token or not token_generated_at:
        return False
    hours_elapsed = (datetime.now() - token_generated_at).total_seconds() / 3600
    return hours_elapsed < 20  # 20 hours safe margin

def get_token():
    if is_token_valid():
        return access_token
    else:
        send_telegram_message("⚠️ Token expired or missing.\nPlease visit /login to re-authenticate.")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO ORDER PLACEMENT (Upstox API)
# ═══════════════════════════════════════════════════════════════════════════════
def place_order(symbol, qty, order_type='MARKET', transaction_type='BUY', price=0):
    token = get_token()
    if not token:
        logger.error("Cannot place order: Token not available")
        return {"error": "Token not available. Visit /login"}

    url = "https://api.upstox.com/v2/order/place"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    payload = {
        "quantity": int(qty),
        "product": "I",  # Intraday
        "order_type": order_type,
        "transaction_type": transaction_type,
        "trading_symbol": symbol,
        "exchange": "NSE",  # Change if needed (BSE, NFO, etc.)
        "validity": "DAY",
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False
    }
    if order_type == 'LIMIT':
        payload["price"] = price

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        order_data = response.json()
        logger.info(f"Order placed: {transaction_type} {symbol} - {order_data}")
        send_telegram_message(f"📈 <b>ORDER PLACED</b>\n{transaction_type} {symbol} | Qty: {qty}\nOrder ID: {order_data.get('data', {}).get('order_id')}")
        return order_data
    else:
        logger.error(f"Order failed: {response.text}")
        send_telegram_message(f"❌ Order failed for {symbol}: {response.text}")
        return {"error": response.text}

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    token_status = "✅ Active" if is_token_valid() else "❌ Expired/Missing"
    return jsonify({
        'bot': 'ICT Pro Bot V7.0',
        'status': 'active',
        'trades_today': tracker.daily_stats['total_trades'],
        'upstox_token': token_status,
        'login_url': f"{request.url_root}login"
    })

@app.route('/login')
def login():
    if not UPSTOX_API_KEY or not UPSTOX_API_SECRET:
        return "Error: Upstox credentials missing in environment!", 500
    auth_url = (
        "https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={UPSTOX_API_KEY}&redirect_uri={UPSTOX_REDIRECT_URI}"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "<h2>❌ Error: No authorization code received</h2>", 400
    if generate_access_token(code):
        return """
        <h1 style="color:green;">✅ SUCCESS!</h1>
        <h2>Upstox Token Generated!</h2>
        <p>Bot अब live trading के लिए तैयार है।</p>
        <p><a href="/">← Back</a></p>
        """
    else:
        return "<h2 style='color:red;'>❌ Token Generation Failed</h2>", 500

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400

        action = data.get('action', '').upper()
        symbol = data.get('symbol')
        qty = safe_float(data.get('qty'), 1)
        price = safe_float(data.get('price'))

        if not symbol:
            return jsonify({'status': 'error', 'message': 'Symbol missing'}), 400

        if action == 'BUY':
            message = format_buy_alert(data)
            tracker.add_trade(data)
            # Auto place BUY order
            place_order(symbol, qty, 'MARKET', 'BUY')
        elif action == 'SELL':
            message = format_sell_alert(data)
            tracker.add_trade(data)
            # Auto place SELL order
            place_order(symbol, qty, 'MARKET', 'SELL')
        elif action in ['CLOSE', 'PARTIAL_CLOSE']:
            pnl_pct = safe_float(data.get('pnl_percent', 0))
            tracker.update_pnl(pnl_pct)
            message = format_close_alert(data)
        else:
            return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

        send_telegram_message(message)
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-buy', methods=['GET'])
def test_buy():
    place_order('RELIANCE', 1, 'MARKET', 'BUY')
    return jsonify({'status': 'Test BUY order placed'})

@app.route('/test-sell', methods=['GET'])
def test_sell():
    place_order('RELIANCE', 1, 'MARKET', 'SELL')
    return jsonify({'status': 'Test SELL order placed'})

# बाकी routes (test, stats, summary) same as before
@app.route('/test', methods=['GET'])
def test_alert():
    test_data = {
        'action': 'BUY', 'symbol': 'RELIANCE', 'price': 2450.50, 'sl': 2400.00,
        'tp': 2650.00, 'qty': 1, 'risk': 500.00, 'rr': 4.0,
        'regime': 'TRENDING', 'confluence': 12, 'killzone': 'NSE Session'
    }
    message = format_buy_alert(test_data)
    send_telegram_message(message)
    return jsonify({'status': 'Test alert sent'})

@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        'daily_stats': tracker.daily_stats,
        'win_rate': tracker.get_win_rate(),
        'total_trades': len(tracker.trades),
        'upstox_token_valid': is_token_valid()
    })

@app.route('/summary', methods=['POST'])
def daily_summary():
    message = format_daily_summary()
    send_telegram_message(message)
    tracker.reset_daily_stats()
    return jsonify({'status': 'success'})

# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════════
def daily_summary_scheduler():
    while True:
        now = datetime.now()
        if now.hour == 15 and now.minute == 30:
            message = format_daily_summary()
            send_telegram_message(message)
            tracker.reset_daily_stats()
            time.sleep(70)
        time.sleep(30)

def send_startup_message():
    message = f"""
🤖 <b>ICT PRO BOT V7.0 STARTED</b> 🤖
━━━━━━━━━━━━━━━━━━━━━
✅ Status: Running
📅 {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
🔑 Token: {'✅ Valid' if is_token_valid() else '❌ Login Required → /login'}
📈 Auto Trading: ENABLED
━━━━━━━━━━━━━━━━━━━━━
"""
    send_telegram_message(message)

if __name__ == '__main__':
    send_startup_message()
    Thread(target=daily_summary_scheduler, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)