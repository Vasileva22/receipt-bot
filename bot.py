import json
import os
from threading import Thread
import telebot
import google.generativeai as genai
from flask import Flask

# Получаем токен телеграма из окружения, а ключ Gemini пропишем напрямую
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = "AQ.Ab8RN6LmjaMmY9KHF8JJIc4ULeh1j0na95WKR-IK9qHj-6dneg"

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Создаем простой веб-сервер для Render, чтобы он видел открытый порт
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

    temp_filename = "temp_receipt.jpg"
    with open(temp_filename, "wb") as new_file:
      new_file.write(downloaded_file)

    sample_file = genai.upload_file(
        path=temp_filename, display_name="Receipt"
    )

    prompt = (
        "Проанализируй этот чек и верни данные строго в формате JSON со"
        ' следующими ключами: "date", "total", "tax_rate", "tax_amount",'
        ' "net_amount", "content", "city", "creditor", "person", "description".'
        " Колонки: TARİH, TUTAR(KDV DAHİL), KDV ORANI (%), KDV TUTARI,"
        " TUTAR(KDV HARİÇ), İÇERİK, ŞEHİR, ALACAKLI, PERSONEL, AÇIKLAMALAR."
        " Возвращай только чистый JSON без лишнего текста."
    )

    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content([sample_file, prompt])

    result_text = response.text.strip()
    if result_text.startswith("```json"):
      result_text = result_text[7:-3].strip()

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


# Запускаем веб-сервер и бот с защитой от конфликтов
if __name__ == "__main__":
  t = Thread(target=run_web)
  t.start()
  print("Бот и веб-сервер запущены...")
  bot.remove_webhook()
  bot.infinity_polling(timeout=60, long_polling_timeout=60)
