# scihub_handler.py
from Bot.scihub.scihub import SciHubClient
import os

scihub_client = SciHubClient()

def handle_scihub_command(bot, message):
    text = (
        "🔗 *Descarga de artículos científicos*\n\n"
        "Envía un DOI o URL de un artículo científico, o usa el comando:\n"
        "`/doi <DOI o URL>`\n\n"
        "Ejemplo:\n"
        "`/doi 10.1038/s41586-019-1750-x`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

def process_doi_command(bot, message):
    import re
    # Extrae el DOI o URL del mensaje
    text = message.text
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Por favor, envía el comando seguido del DOI o URL.\nEjemplo:\n/doi 10.1038/s41586-019-1750-x")
        return
    query = parts[1].strip()
    bot.send_chat_action(message.chat.id, "upload_document")
    pdf_url = scihub_client.search_pdf_url(query)
    if pdf_url:
        try:
            import requests
            filename = query.replace("/", "_") + ".pdf"
            r = requests.get(pdf_url, stream=True, timeout=15)
            if r.status_code == 200:
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                with open(filename, "rb") as f:
                    bot.send_document(message.chat.id, f)
                os.remove(filename)
            else:
                bot.send_message(message.chat.id, "❌ Error descargando el PDF.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error enviando el PDF: {e}")
    else:
        bot.send_message(message.chat.id, "❌ No se encontró el paper en Sci-Hub.")
