import json
import os
import telebot
import gspread
import google.generativeai as genai

# Получаем ключи из окружения Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настраиваем Gemini
genai.configure(api_key=GEMINI_API_KEY)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Ссылка на твою Google Таблицу «Romanya 2026»
SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1IdIGkRbco0NV-sa1fBBb38O3nkzA0gqIvlIfoDA-_Pg/edit?usp=sharing"
)

# Открываем таблицу публично по ссылке (убедись, что в таблице стоит доступ «Все, у кого есть ссылка -> Редактор»)
gc = gspread.service_account(filename=None)  # Заглушка, но проще открыть через публичный клиент:
client = gspread.Client(auth=None)
sheet = client.open_by_url(SPREADSHEET_URL).sheet1


@bot.message_handler(commands=["start"])
def send_welcome(bot_message):
  bot.reply_to(
      bot_message,
      "Привет! Скинь мне фото или PDF чека, а я заполню таблицу «Romanya"
      " 2026».",
  )


@bot.message_handler(content_types=["photo", "document"])
def handle_receipt(message):
  try:
    bot.reply_to(message, "⏳ Обрабатываю чек...")

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

    row = [
        data.get("date", ""),
        data.get("total", ""),
        data.get("tax_rate", ""),
        data.get("tax_amount", ""),
        data.get("net_amount", ""),
        data.get("content", ""),
        data.get("city", ""),
        data.get("creditor", ""),
        data.get("person", ""),
        data.get("description", ""),
    ]

    sheet.append_row(row)
    bot.reply_to(message, "✅ Чек успешно распознан и добавлен в таблицу!")

  except Exception as e:
    bot.reply_to(message, f"❌ Произошла ошибка при обработке чека: {e}")


print("Бот запущен...")
bot.infinity_polling()
