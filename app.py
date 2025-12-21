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
# 📱 CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = "8520294976:AAG7cvsDUECK2kbwIzqCCj3yRSeBPeY-4O8"
CHAT_ID = "7340945498"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

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
        """Add new trade to tracking"""
        self.trades.append({
            'timestamp': datetime.now().isoformat(),
            'data': trade_data
        })
        self.daily_stats['total_trades'] += 1
        logger.info(f"Trade added: {trade_data.get('symbol')} - {trade_data.get('action')}")

    def update_pnl(self, pnl):
        """Update P&L tracking"""
        self.daily_stats['total_pnl'] += pnl
        if pnl > 0:
            self.daily_stats['winning_trades'] += 1
        else:
            self.daily_stats['losing_trades'] += 1

    def get_win_rate(self):
        """Calculate win rate"""
        total = self.daily_stats['total_trades']
        if total == 0:
            return 0
        return (self.daily_stats['winning_trades'] / total) * 100

    def reset_daily_stats(self):
        """Reset daily statistics"""
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
    """Send message to Telegram"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        response = requests.post(url, json=payload, timeout=10)

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
    """Format BUY signal alert"""
    symbol = data.get('symbol', 'N/A')
    price = data.get('price', 0)
    sl = data.get('sl', 0)
    tp = data.get('tp', 0)
    qty = data.get('qty', 0)
    risk = data.get('risk', 0)
    rr = data.get('rr', 0)
    regime = data.get('regime', 'N/A')
    confluence = data.get('confluence', 0)
    killzone = data.get('killzone', 'N/A')

    # Calculate Risk-Reward details
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
    return message

def format_sell_alert(data):
    """Format SELL signal alert"""
    symbol = data.get('symbol', 'N/A')
    price = data.get('price', 0)
    sl = data.get('sl', 0)
    tp = data.get('tp', 0)
    qty = data.get('qty', 0)
    risk = data.get('risk', 0)
    rr = data.get('rr', 0)
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
    return message

def format_close_alert(data):
    """Format position close alert"""
    symbol = data.get('symbol', 'N/A')
    pnl_pct = data.get('pnl_percent', 0)
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
    return message

def format_daily_summary():
    """Format end-of-day summary"""
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
    return message

# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'active',
        'bot': 'ICT Pro Bot V7.0',
        'version': '2026 Edition',
        'uptime': 'Running',
        'trades_today': tracker.daily_stats['total_trades']
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive TradingView webhook alerts"""
    try:
        # Get JSON data from TradingView
        data = request.get_json()

        if not data:
            logger.warning("Received empty webhook data")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        logger.info(f"Webhook received: {json.dumps(data, indent=2)}")

        # Parse action type
        action = data.get('action', '').upper()

        # Send appropriate alert based on action
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
            logger.warning(f"Unknown action received: {action}")
            return jsonify({'status': 'error', 'message': 'Unknown action'}), 400

        # Send to Telegram
        send_telegram_message(message)

        return jsonify({
            'status': 'success',
            'message': 'Alert sent to Telegram',
            'action': action
        }), 200

    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/test', methods=['GET'])
def test_alert():
    """Test endpoint to send sample alert"""
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
        'killzone': 'NSE/BSE Session'
    }

    message = format_buy_alert(test_data)
    send_telegram_message(message)

    return jsonify({
        'status': 'success',
        'message': 'Test alert sent to Telegram'
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get current trading statistics"""
    return jsonify({
        'daily_stats': tracker.daily_stats,
        'win_rate': tracker.get_win_rate(),
        'total_trades': len(tracker.trades)
    })

@app.route('/summary', methods=['POST'])
def daily_summary():
    """Send daily summary (can be triggered manually or via cron)"""
    message = format_daily_summary()
    send_telegram_message(message)
    tracker.reset_daily_stats()

    return jsonify({
        'status': 'success',
        'message': 'Daily summary sent'
    })

# ═══════════════════════════════════════════════════════════════════════════════
# 🕐 BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════════

def daily_summary_scheduler():
    """Send daily summary at 3:30 PM IST (end of trading day)"""
    while True:
        now = datetime.now()
        # Check if it's 3:30 PM IST (15:30)
        if now.hour == 15 and now.minute == 30:
            try:
                message = format_daily_summary()
                send_telegram_message(message)
                tracker.reset_daily_stats()
                logger.info("Daily summary sent automatically")
                # Sleep for 60 seconds to avoid duplicate sends
                time.sleep(60)
            except Exception as e:
                logger.error(f"Error in daily summary scheduler: {str(e)}")

        # Check every 30 seconds
        time.sleep(30)

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

def send_startup_message():
    """Send bot startup notification"""
    message = f"""
🤖 <b>ICT PRO BOT V7.0 STARTED</b> 🤖
━━━━━━━━━━━━━━━━━━━━━
✅ <b>Status:</b> Active and Running
📅 <b>Date:</b> {datetime.now().strftime('%d-%m-%Y')}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

🎯 <b>Features Enabled:</b>
• Multi-Bagger Detection ✅
• AI Pattern Recognition ✅
• Smart Money Concepts ✅
• News Event Filter ✅
• Kelly Criterion Sizing ✅

📱 <b>Ready for Signals!</b>
━━━━━━━━━━━━━━━━━━━━━
"""
    send_telegram_message(message)
    logger.info("Startup message sent to Telegram")

if __name__ == '__main__':
    # Send startup notification
    send_startup_message()

    # Start daily summary scheduler in background
    summary_thread = Thread(target=daily_summary_scheduler, daemon=True)
    summary_thread.start()
    logger.info("Daily summary scheduler started")

    # Get port from environment variable (for cloud deployment)
    port = int(os.environ.get('PORT', 5000))

    # Start Flask app
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
