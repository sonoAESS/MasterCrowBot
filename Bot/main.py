import os
import logging
import telebot
from dotenv import load_dotenv
from bot_handler import BotHandler
from handlers import register_handlers

def setup_logging():
    """Configura logging avanzado"""
    # Asegurar que existe el directorio de logs
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot_log.log")

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )
    logger = logging.getLogger(__name__)
    return logger


def main():
    load_dotenv()
    logger = setup_logging()
    logger.info("=== INICIANDO BOT ===")

    # Verificar entorno
    logger.info("Verificando variables de entorno...")
    token = os.getenv("TOKEN")
    if not token:
        logger.critical("ERROR: No se encontró el TOKEN en las variables de entorno")
        return

    try:
        logger.info("Inicializando cliente de Telegram...")
        # Inicializar el bot sin parse_mode Markdown para evitar errores de formato
        bot = telebot.TeleBot(token, parse_mode=None, threaded=True)
        bot.skip_pending = True

        bot_handler = BotHandler(bot=bot)
        register_handlers(bot, bot_handler)

        logger.info("Bot listo, iniciando polling...")
        bot.infinity_polling()
    except Exception as e:
        logger.critical(f"ERROR FATAL iniciando el bot: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
