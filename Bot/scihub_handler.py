from telebot import types
import requests
import os

def handle_scihub_command(bot, message):
    """
    Envía un mensaje explicando cómo usar el comando /doi para descargar papers vía SciHub.

    Args:
        bot: instancia del bot TeleBot
        message: mensaje recibido del usuario
    """
    chat_id = message.chat.id
    ejemplo_doi = "10.1038/s41586-020-2649-2"  # Ejemplo DOI real

    texto = (
        "🔎 *Descarga de artículos con SciHub*\n\n"
        "Para descargar un artículo usando SciHub, envía el comando:\n"
        f"`/doi {ejemplo_doi}`\n\n"
        "Reemplaza el ejemplo con el DOI del artículo que deseas descargar.\n"
        "El bot intentará obtener el artículo correspondiente desde SciHub."
    )

    bot.send_message(chat_id, texto, parse_mode="Markdown")

def process_doi_command(bot, message, doi):
    """
    Procesa el comando /doi recibido, busca el doi en SciHub y envía enlace del archuivo al usuario.

    Args:
        bot: instancia del bot TeleBot
        message: mensaje recibido del usuario
        doi: string con el DOI recibido
    """
    chat_id = message.chat.id
    try:
        bot.send_message(chat_id, f"🔗 Buscando el artículo para el DOI: `{doi}`...", parse_mode="Markdown")
        pdf_url = get_scihub_pdf_url(doi)
        if not pdf_url:
            bot.send_message(chat_id, "❌ No se pudo encontrar el PDF en Sci-Hub.")
            return

        # Solo enviar enlace para evitar timeout
        bot.send_message(chat_id, f"Puedes descargar el artículo aquí:\n{pdf_url}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error al procesar la solicitud: {e}")

def get_scihub_pdf_url(doi):
    """
    Realiza scraping en Sci-Hub para obtener el enlace directo al PDF del artículo.

    Args:
        doi (str): DOI del artículo.

    Returns:
        str|None: URL directa al PDF si se encuentra, None si no.
    """
    # Lista de posibles dominios de Sci-Hub (por si alguno está caído)
    scihub_domains = [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TelegramBot/1.0)"
    }
    for domain in scihub_domains:
        try:
            url = f"{domain}/{doi}"
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                # Analiza el HTML para encontrar el <iframe> que contiene el PDF
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                iframe = soup.find("iframe")
                if iframe and iframe.get("src"):
                    pdf_url = iframe["src"]
                    # Corrige la URL si es relativa
                    if pdf_url.startswith("//"):
                        pdf_url = "https:" + pdf_url
                    elif pdf_url.startswith("/"):
                        pdf_url = domain + pdf_url
                    return pdf_url
        except Exception:
            continue
    return None
