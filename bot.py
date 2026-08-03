import base64
import json
import os
from threading import Thread
import requests
import telebot
from flask import Flask

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

app = Flask("")


@app.route("/")
def home():
  return "Bot is alive!"


def run_web():
  app.run(host="0.0.0.0", port=10000)


@bot.message_handler(commands=["start"])
def send_welcome(bot_message):
  bot.reply_to(
      bot_message,
      "Привет! Скинь мне фото чека, а я мгновенно вытащу из него все данные.",
  )


@bot.message_handler(content_types=["photo", "document"])
def handle_receipt(message):
  try:
    bot.reply_to(message, "⏳ Обрабатываю чек через Gemini...")

    if message.content_type == "photo":
      file_info = bot.get_file(message.photo[-1].file_id)
    else:
      file_info = bot.get_file(message.document.file_id)

    downloaded_file = bot.download_file(file_info.file_path)

    encoded_image = base64.b64encode(downloaded_file).decode("utf-8")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}",
    }

    prompt_text = (
        "Проанализируй этот чек и верни данные строго в формате JSON со"
        ' следующими ключами: "date", "total", "tax_rate", "tax_amount",'
        ' "net_amount", "content", "city", "creditor", "person", "description".'
        " Колонки: TARİH, TUTAR(KDV DAHİL), KDV ORANI (%), KDV TUTARI,"
        " TUTAR(KDV HARİÇ), İÇERİK, ŞEHİR, ALACAKLI, PERSONEL, AÇIKLAMALAR."
        " Возвращай только чистый JSON без лишнего текста и без markdown-разметки."
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_text},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": encoded_image,
                    }
                },
            ]
        }]
    }

    response = requests.post(
        url, headers=headers, data=json.dumps(payload), timeout=30
    )

    if response.status_code != 200:
      raise Exception(f"Ошибка API Google: {response.text}")

    res_json = response.json()
    result_text = (
        res_json.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "{}")
        .strip()
    )

    if result_text.startswith("```json"):
      result_text = result_text[7:-3].strip()
    elif result_text.startswith("```"):
      result_text = result_text[3:-3].strip()

    data = json.loads(result_text)

    formatted_answer = (
        f"✅ **Чек успешно распознан!**\n\n"
        f"📅 **Дата:** {data.get('date', '')}\n"
        f"💰 **Сумма (с НДС):** {data.get('total', '')}\n"
        f"📊 **НДС (%):** {data.get('tax_rate', '')}\n"
        f"📉 **Сумма НДС:** {data.get('tax_amount', '')}\n"
        f"💵 **Сумма (без НДС):** {data.get('net_amount', '')}\n"
        f"📦 **Содержимое:** {data.get('content', '')}\n"
        f"🏙 **Город:** {data.get('city', '')}\n"
        f"🏢 **Продавец:** {data.get('creditor', '')}\n"
        f"👤 **Сотрудник:** {data.get('person', '')}\n"
        f"📝 **Описание:** {data.get('description', '')}"
    )

    bot.reply_to(message, formatted_answer, parse_mode="Markdown")

  except Exception as e:
    bot.reply_to(message, f"❌ Произошла ошибка: {e}")


if __name__ == "__main__":
  t = Thread(target=run_web)
  t.start()
  print("Бот и веб-сервер запущены...")
  bot.remove_webhook()
  bot.infinity_polling(timeout=60, long_polling_timeout=60)
