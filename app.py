#!/usr/bin/env python3
"""
ICT PRO BOT V7.0 - Telegram Alert System
Receives TradingView webhooks and sends detailed alerts to Telegram
"""

from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime
import logging
import os
from threading import Thread
import time

# ═══════════════════════════════════════════════════════════════════════════════
# 📱 CONFIGURATION (Better: Use Environment Variables for Security)
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8520294976:AAG7cvsDUECK2kbwIzqCCj3yRSeBPeY-4O8")
CHAT_ID = os.environ.get("CHAT_ID", "7340945498")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Flask App Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ict-pro-bot-v7-2026'

# Logging Setup
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
# 💾 TRADE TRACKING
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
        self.trades.append({
            'timestamp': datetime.now().isoformat(),
            'data': trade_data
        })
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
# 📱 TELEGRAM FUNCTIONS
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
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False

def format_buy_alert(data):
    symbol = data.get('symbol', 'N/A')
    price = float(data.get('price', 0))
    sl = float(data.get('sl', 0))
    tp = float(data.get('tp', 0))
    qty = float(data.get('qty', 0))
    risk = float(data.get('risk', 0))
    rr = float(data.get('rr', 0))
    regime = data.get('regime', 'N/A')
    confluence = data.get('confluence', 0)
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
    price = float(data.get('price', 0))
    sl = float(data.get('sl', 0))
    tp = float(data.get('tp', 0))
    qty = float(data.get('qty', 0))
    risk = float(data.get('risk', 0))
    rr = float(data.get('rr', 0))
    regime = data.get('regime', 'N/A')
    confluence = data.get('confluence', 0)
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

# Baki functions same (format_close_alert, format_daily_summary, etc.)

# ... (format_close_alert aur format_daily_summary same rakho jo tumhare code mein the)

# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK ROUTES (Fixed with safe float conversion)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400

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
        logger.error(f"Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Baki routes (/test, /stats, etc.) same rakho

if __name__ == '__main__':
    send_startup_message()
    summary_thread = Thread(target=daily_summary_scheduler, daemon=True)
    summary_thread.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
