import json
import os
from threading import Thread
from google import genai
from google.genai import types
import telebot
from flask import Flask

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Инициализируем новый официальный клиент Google GenAI
client = genai.Client(api_key=GEMINI_API_KEY)

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
      "Привет! Скинь мне фото чека, а я мгновенно вытащу из него все данные"
      " через Gemini.",
  )


@bot.message_handler(content_types=["photo", "document"])
def handle_receipt(message):
  try:
    bot.reply_to(message, "⏳ Обрабатываю чек через официальный Gemini SDK...")

    if message.content_type == "photo":
      file_info = bot.get_file(message.photo[-1].file_id)
    else:
      file_info = bot.get_file(message.document.file_id)

    downloaded_file = bot.download_file(file_info.file_path)

    prompt_text = (
        "Проанализируй этот чек и верни данные строго в формате JSON со"
        ' следующими ключами: "date", "total", "tax_rate", "tax_amount",'
        ' "net_amount", "content", "city", "creditor", "person", "description".'
        " Колонки: TARİH, TUTAR(KDV DAHİL), KDV ORANI (%), KDV TUTARI,"
        " TUTAR(KDV HARİÇ), İÇERİK, ŞEHİR, ALACAKLI, PERSONEL, AÇIKLAMALAR."
        " Возвращай только чистый JSON без лишнего текста и без markdown-разметки."
    )

    # Используем стабильную модель gemini-2.0-flash
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=downloaded_file, mime_type="image/jpeg"),
            prompt_text,
        ],
    )

    result_text = response.text.strip()

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
