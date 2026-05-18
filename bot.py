import os
import time
import json
import requests
from datetime import datetime

# API Keys
TELEGRAM_TOKEN = "8727086511:AAGGlyy7YlV1XDDARqf4A50QXIm_0Fab9EM"
POLYGON_KEY = "n53ZBwc6KrD8VZnEfldynN42rY9XXnqr"
CLAUDE_KEY = "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"

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF", 
         "USD/CAD", "EUR/JPY", "EUR/CHF", "AUD/JPY", "CAD/JPY",
         "CHF/JPY", "EUR/AUD", "EUR/CAD", "AUD/CHF", "AUD/CAD"]

TIMEFRAMES = ["1 دقيقة", "5 دقائق", "30 دقيقة", "1 ساعة"]

user_state = {}

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TELEGRAM_API}/sendMessage", json=data)

def send_main_menu(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📊 تحليل صفقة جديدة", "callback_data": "new_trade"}],
            [{"text": "ℹ️ حالة السوق", "callback_data": "market_status"}]
        ]
    }
    send_message(chat_id, "👋 <b>مرحباً في Forex Analyzer</b>\n\nاختر ما تريد:", keyboard)

def send_pairs_menu(chat_id):
    rows = []
    row = []
    for i, pair in enumerate(PAIRS):
        row.append({"text": pair, "callback_data": f"pair_{pair}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "🔙 رجوع", "callback_data": "back"}])
    keyboard = {"inline_keyboard": rows}
    send_message(chat_id, "💱 <b>اختر زوج العملات:</b>", keyboard)

def send_timeframe_menu(chat_id, pair):
    keyboard = {
        "inline_keyboard": [
            [{"text": "1 دقيقة", "callback_data": "tf_1min"},
             {"text": "5 دقائق", "callback_data": "tf_5min"}],
            [{"text": "30 دقيقة", "callback_data": "tf_30min"},
             {"text": "1 ساعة", "callback_data": "tf_1h"}],
            [{"text": "🔙 رجوع", "callback_data": "new_trade"}]
        ]
    }
    send_message(chat_id, f"⏱ <b>اختر مدة الصفقة لـ {pair}:</b>", keyboard)

def get_market_data(symbol):
    try:
        sym = symbol.replace("/", "")
        from_cur = symbol.split("/")[0]
        to_cur = symbol.split("/")[1]
        
        # Get current price from Polygon
        url = f"https://api.polygon.io/v2/last/trade/{sym}?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        # Try forex endpoint
        url2 = f"https://api.polygon.io/v2/aggs/ticker/C:{sym}/prev?adjusted=true&apiKey={POLYGON_KEY}"
        r2 = requests.get(url2, timeout=10)
        data2 = r2.json()
        
        price = None
        if data2.get("results"):
            price = data2["results"][0]["c"]
        
        return {"price": price, "symbol": symbol}
    except:
        return {"price": None, "symbol": symbol}

def analyze_with_claude(symbol, timeframe, price):
    try:
        now = datetime.now()
        hour = now.hour
        
        if 16 <= hour < 20:
            session = "London/NY Overlap (الأفضل)"
        elif 11 <= hour < 16:
            session = "London"
        elif 20 <= hour or hour < 2:
            session = "New York"
        elif 3 <= hour < 11:
            session = "Tokyo"
        else:
            session = "Sydney"

        price_str = f"{price:.5f}" if price else "غير متوفر"
        
        prompt = f"""أنت محلل Forex محترف. حلل {symbol} لصفقة {timeframe}.
الوقت: {now.strftime('%H:%M')} | الجلسة: {session}
السعر الحالي: {price_str}

قواعد التحليل:
1. حلل الاتجاه الحالي بناءً على وقت الجلسة والزوج
2. RSI: أقل من 30=شراء قوي، أكثر من 70=بيع قوي
3. MACD: إيجابي=شراء، سلبي=بيع
4. Bollinger: قرب الحد السفلي=شراء، العلوي=بيع
5. MA20: السعر فوقها=شراء، تحتها=بيع

مهم جداً:
- أعطِ BUY أو SELL فقط — لا WAIT أبداً
- الثقة بين 65-90% دائماً
- كن حاسماً وواضحاً

أجب بـ JSON فقط:
{{"signal":"BUY or SELL","confidence":"65-90","rsi":"number","macd":"positive or negative","trend":"Uptrend or Downtrend","support":"level","resistance":"level","reason":"سببان واضحان بالعربي"}}"""

        headers = {
            "Content-Type": "application/json",
            "x-api-key": CLAUDE_KEY,
            "anthropic-version": "2023-06-01"
        }
        body = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 500,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}]
        }
        
        r = requests.post("https://api.anthropic.com/v1/messages", 
                         headers=headers, json=body, timeout=30)
        data = r.json()
        
        if data.get("error"):
            return None
            
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
            
        return json.loads(text[start:end+1])
    except Exception as e:
        print(f"Claude error: {e}")
        return None

def format_result(symbol, timeframe, result, price):
    signal = result.get("signal", "N/A")
    conf = result.get("confidence", "N/A")
    rsi = result.get("rsi", "N/A")
    macd = result.get("macd", "N/A")
    trend = result.get("trend", "N/A")
    support = result.get("support", "N/A")
    resistance = result.get("resistance", "N/A")
    reason = result.get("reason", "")
    
    emoji = "🟢" if signal == "BUY" else "🔴"
    signal_ar = "شراء" if signal == "BUY" else "بيع"
    trend_ar = "صاعد" if "Up" in trend else "هابط"
    macd_ar = "إيجابي" if macd == "positive" else "سلبي"
    
    price_str = f"{float(price):.5f}" if price else "N/A"
    
    strength = "قوي جداً 💪" if int(conf) >= 80 else "متوسط" if int(conf) >= 70 else "ضعيف"
    
    msg = f"""
{emoji} <b>{signal_ar} — {symbol}</b>

📌 <b>معلومات الصفقة:</b>
• المدة: {timeframe}
• السعر: {price_str}
• الثقة: {conf}% ({strength})

📊 <b>المؤشرات:</b>
• RSI: {rsi}
• MACD: {macd_ar}
• الاتجاه: {trend_ar}
• الدعم: {support}
• المقاومة: {resistance}

💡 <b>التحليل:</b>
{reason}

⚠️ للمعلومات فقط — القرار النهائي لك
"""
    return msg

def process_update(update):
    try:
        if "callback_query" in update:
            query = update["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            data = query["data"]
            msg_id = query["message"]["message_id"]
            
            # Answer callback
            requests.post(f"{TELEGRAM_API}/answerCallbackQuery", 
                         json={"callback_query_id": query["id"]})
            
            if data == "new_trade" or data == "back":
                user_state[chat_id] = {}
                send_pairs_menu(chat_id)
                
            elif data == "market_status":
                now = datetime.now()
                h = now.hour
                if 16 <= h < 20:
                    status = "⭐ تداخل لندن/نيويورك — أفضل وقت!"
                elif 11 <= h < 16:
                    status = "✅ جلسة لندن مفتوحة"
                elif 20 <= h or h < 2:
                    status = "✅ جلسة نيويورك مفتوحة"
                elif 3 <= h < 11:
                    status = "🌸 جلسة طوكيو — إشارات متوسطة"
                else:
                    status = "⚠️ نشاط منخفض"
                
                send_message(chat_id, f"🕐 <b>حالة السوق</b>\n\n{status}\n\nالوقت: {now.strftime('%H:%M')}")
                
            elif data.startswith("pair_"):
                pair = data.replace("pair_", "")
                user_state[chat_id] = {"pair": pair}
                send_timeframe_menu(chat_id, pair)
                
            elif data.startswith("tf_"):
                tf_map = {"tf_1min": "1 دقيقة", "tf_5min": "5 دقائق", 
                          "tf_30min": "30 دقيقة", "tf_1h": "1 ساعة"}
                timeframe = tf_map.get(data, "5 دقائق")
                pair = user_state.get(chat_id, {}).get("pair", "EUR/USD")
                
                send_message(chat_id, f"⏳ <b>جاري تحليل {pair}...</b>\nانتظر لحظة...")
                
                # Get real data
                market_data = get_market_data(pair)
                price = market_data.get("price")
                
                # Analyze with Claude
                result = analyze_with_claude(pair, timeframe, price)
                
                if result:
                    msg = format_result(pair, timeframe, result, price)
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🔄 تحليل جديد لنفس الزوج", "callback_data": f"tf_{data.replace('tf_', '')}"}],
                            [{"text": "💱 تغيير الزوج", "callback_data": "new_trade"}]
                        ]
                    }
                    send_message(chat_id, msg, keyboard)
                else:
                    send_message(chat_id, "❌ حدث خطأ. حاول مرة أخرى.")
                    
        elif "message" in update:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "")
            
            if text == "/start":
                send_message(chat_id, "👋 <b>مرحباً في Forex Analyzer!</b>\n\nبوت تحليل العملات الاحترافي")
                time.sleep(0.5)
                send_main_menu(chat_id)
    except Exception as e:
        print(f"Error processing update: {e}")

def main():
    print("🚀 Bot started!")
    offset = 0
    
    while True:
        try:
            r = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            updates = r.json().get("result", [])
            
            for update in updates:
                offset = update["update_id"] + 1
                process_update(update)
                
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
