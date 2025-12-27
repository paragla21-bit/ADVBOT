#!/usr/bin/env python3
"""
ICT PRO BOT V7.0 - Telegram Alert System
AUTO CODE GENERATION SYSTEM - No Manual Daily Generation Needed
"""

from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime, timedelta
import logging
import os
from threading import Thread
import time
import secrets
import hashlib

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8520294976:AAG7cvsDUECK2kbwIzqCCj3yRSeBPeY-4O8")
CHAT_ID = os.environ.get("CHAT_ID", "7340945498")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ict-pro-bot-v7-2026'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO CODE GENERATION SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class AutoCodeGenerator:
    def __init__(self):
        self.current_code = self.generate_daily_code()
        self.code_date = datetime.now().date()
        self.code_history = []
        
    def generate_daily_code(self):
        """Generate unique secure code for today"""
        today = datetime.now().strftime('%Y%m%d')
        random_part = secrets.token_hex(4)
        combined = f"{today}{random_part}"
        hash_code = hashlib.sha256(combined.encode()).hexdigest()[:8].upper()
        return f"ICT{today[-4:]}{hash_code}"
    
    def get_current_code(self):
        """Get valid code - auto-regenerate if date changed"""
        today = datetime.now().date()
        if today != self.code_date:
            self.code_history.append({
                'code': self.current_code,
                'date': self.code_date.isoformat(),
                'expired': True
            })
            self.current_code = self.generate_daily_code()
            self.code_date = today
            logger.info(f"New daily code generated: {self.current_code}")
        return self.current_code
    
    def validate_code(self, code):
        """Validate if code is current"""
        return code == self.get_current_code()
    
    def get_code_expiry(self):
        """Get time until code expires"""
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_left = tomorrow - datetime.now()
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"

code_generator = AutoCodeGenerator()

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
# TELEGRAM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def send_telegram_message(message, parse_mode='HTML'):
    try:
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram message sent successfully")
            return True
        else:
            logger.error(f"Telegram error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        return False


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, str) and "{{" in value:
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

    if sl == 0 and risk > 0:
        sl = price - risk
    if tp == 0 and risk > 0:
        tp = price + (risk * rr)

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

    if sl == 0 and risk > 0:
        sl = price + risk
    if tp == 0 and risk > 0:
        tp = price - (risk * rr)

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
    except (ValueError, TypeError):
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
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    current_code = code_generator.get_current_code()
    return jsonify({
        'status': 'active',
        'bot': 'ICT Pro Bot V7.0 - Auto Code System',
        'trades_today': tracker.daily_stats['total_trades'],
        'current_code': current_code,
        'code_expires_in': code_generator.get_code_expiry(),
        'message': 'Use /getcode endpoint to get today\'s access code'
    })

@app.route('/getcode', methods=['GET'])
def get_code():
    """Get today's auto-generated access code"""
    current_code = code_generator.get_current_code()
    expiry = code_generator.get_code_expiry()
    
    message = f"""
🔐 <b>TODAY'S ACCESS CODE</b> 🔐
━━━━━━━━━━━━━━━━━━━━━
📅 <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}
🔑 <b>Code:</b> <code>{current_code}</code>

⏰ <b>Valid For:</b> {expiry}
🔄 <b>Auto-Renews:</b> Daily at 12:00 AM

💡 <b>Usage:</b>
Send POST to /webhook with:
{{"code": "{current_code}", ...}}

━━━━━━━━━━━━━━━━━━━━━
"""
    
    send_telegram_message(message)
    
    return jsonify({
        'status': 'success',
        'code': current_code,
        'valid_until': expiry,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'message': 'Code sent to Telegram'
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400

        # Validate code if provided
        provided_code = data.get('code')
        if provided_code and not code_generator.validate_code(provided_code):
            return jsonify({
                'status': 'error', 
                'message': 'Invalid or expired code. Use /getcode to get current code.'
            }), 401

        logger.info(f"Webhook received: {json.dumps(data)}")
        action = data.get('action', '').upper()

        if action == 'BUY':
            message = format_buy_alert(data)
            tracker.add_trade(data)
        elif action == 'SELL':
            message = format_sell_alert(data)
            tracker.add_trade(data)
        elif action in ['CLOSE', 'PARTIAL_CLOSE']:
            pnl_pct = float(data.get('pnl_percent', 0))
            tracker.update_pnl(pnl_pct)
            message = format_close_alert(data)
        else:
            return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

        send_telegram_message(message)
        return jsonify({'status': 'success', 'action': action}), 200

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/test', methods=['GET'])
def test_alert():
    test_data = {
        'action': 'BUY',
        'symbol': 'RELIANCE',
        'price': 2450.50,
        'sl': 2400.00,
        'tp': 2650.00,
        'qty': 10,
        'risk': 500.00,
        'rr': 4.0,
        'regime': 'TRENDING',
        'confluence': 12,
        'killzone': 'NSE/BSE Session',
        'code': code_generator.get_current_code()
    }
    message = format_buy_alert(test_data)
    send_telegram_message(message)
    return jsonify({'status': 'success', 'message': 'Test alert sent'})

@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        'daily_stats': tracker.daily_stats,
        'win_rate': tracker.get_win_rate(),
        'total_trades': len(tracker.trades),
        'current_code': code_generator.get_current_code(),
        'code_expires_in': code_generator.get_code_expiry()
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
def daily_code_announcer():
    """Announce new code every morning"""
    while True:
        now = datetime.now()
        # Send new code at 9:00 AM every day
        if now.hour == 9 and now.minute == 0:
            current_code = code_generator.get_current_code()
            message = f"""
🌅 <b>GOOD MORNING!</b> 🌅
━━━━━━━━━━━━━━━━━━━━━
📅 <b>{datetime.now().strftime('%A, %d %B %Y')}</b>

🔑 <b>Today's Access Code:</b>
<code>{current_code}</code>

✅ Ready for trading signals!
🤖 ICT PRO BOT V7.0 Active

━━━━━━━━━━━━━━━━━━━━━
"""
            send_telegram_message(message)
            time.sleep(60)
        time.sleep(30)

def daily_summary_scheduler():
    """Send summary at market close"""
    while True:
        now = datetime.now()
        if now.hour == 15 and now.minute == 30:
            message = format_daily_summary()
            send_telegram_message(message)
            tracker.reset_daily_stats()
            time.sleep(60)
        time.sleep(30)

def send_startup_message():
    current_code = code_generator.get_current_code()
    message = f"""
🤖 <b>ICT PRO BOT V7.0 STARTED</b> 🤖
━━━━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> Active & Running
📅 <b>{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</b>

🔐 <b>Auto Code System:</b> ENABLED
🔑 <b>Current Code:</b> <code>{current_code}</code>
⏰ <b>Expires In:</b> {code_generator.get_code_expiry()}

📱 <b>Ready for Live Signals!</b>
🔄 <b>Code Auto-Renews Daily</b>
━━━━━━━━━━━━━━━━━━━━━
"""
    send_telegram_message(message)

if __name__ == '__main__':
    send_startup_message()
    Thread(target=daily_code_announcer, daemon=True).start()
    Thread(target=daily_summary_scheduler, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)