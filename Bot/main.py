import os
import logging
import telebot
import time
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot_handler import BotHandler


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


def register_handlers(bot, bot_handler: BotHandler):
    """Registra todos los handlers del bot"""
    logger = logging.getLogger(__name__)
    start_time = time.time()
    logger.info("Iniciando registro de handlers...")

    # Comandos principales
    @bot.message_handler(commands=["start"])
    def start(message):
        logger.info(f"Comando /start recibido de usuario {message.from_user.id}")
        bot_handler.start(message)

    @bot.message_handler(commands=["ask"])
    def ask(message):
        logger.info(
            f"Comando /ask recibido de usuario {message.from_user.id}: '{message.text}'"
        )
        bot_handler.handle_general_question(message)

    @bot.message_handler(commands=["search"])
    def search(message):
        logger.info(
            f"Comando /search recibido de usuario {message.from_user.id}: '{message.text}'"
        )
        bot_handler.handle_embedding_search(message)

    @bot.message_handler(commands=["help"])
    def help_command(message):
        logger.info(f"Comando /help recibido de usuario {message.from_user.id}")
        bot_handler.show_help(message)
    
    @bot.message_handler(commands=["ask"])
    def ask(message):
        logger.info(
            f"Comando /ask recibido de usuario {message.from_user.id}: '{message.text}'"
        )
        bot_handler.handle_general_question(message)

    @bot.message_handler(commands=["doi"])
    def doi(message):
        logger.info(
            f"Comando /doi recibido de usuario {message.from_user.id}: '{message.text}'"
        )
        bot_handler.handle_message(message)

    # Callbacks para interacciones con botones
    @bot.callback_query_handler(func=lambda call: call.data.startswith("list_"))
    def callback_list(call):
        logger.info(
            f"Callback list_{call.data[5:]} recibido de usuario {call.from_user.id}"
        )
        bot_handler.handle_list(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("download#"))
    def callback_download(call):
        doc_path = call.data.replace("download#", "")
        logger.info(
            f"Solicitud de descarga recibida de usuario {call.from_user.id}: {doc_path}"
        )
        bot_handler.handle_pdf_download(call)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("back_"))
    def callback_back(call):
        logger.info(
            f"Callback back recibido de usuario {call.from_user.id}: {call.data}"
        )
        bot_handler.handle_back(call)

    @bot.callback_query_handler(func=lambda call: call.data == "show_help")
    def callback_show_help(call):
        logger.info(f"Callback show_help recibido de usuario {call.from_user.id}")
        bot_handler.show_help(call)

    @bot.callback_query_handler(func=lambda call: call.data == "search_help")
    def callback_search_help(call):
        logger.info(f"Callback search_help recibido de usuario {call.from_user.id}")
        bot_handler.start(call)

    # Mensajes de texto y comandos no reconocidos
    @bot.message_handler(func=lambda message: True, content_types=["text"])
    def handle_text(message):
        if message.text.startswith("/"):
            logger.info(
                f"Comando desconocido recibido de usuario {message.from_user.id}: '{message.text}'"
            )
            bot_handler.show_help(message)
        else:
            logger.info(
                f"Mensaje de texto recibido de usuario {message.from_user.id} ({len(message.text)} caracteres)"
            )
            bot_handler.handle_message(message)

    elapsed_time = time.time() - start_time
    logger.info(
        f"Registrados manejadores de comandos, callbacks y mensajes en {elapsed_time:.2f} segundos"
    )


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
        logger.info("Bot telebot inicializado correctamente")

        logger.info("Creando instancia de BotHandler...")
        start_time = time.time()
        bot_handler = BotHandler(bot=bot)  # Pasar la instancia del bot al handler
        elapsed_time = time.time() - start_time
        logger.info(f"BotHandler inicializado en {elapsed_time:.2f} segundos")

        logger.info("Registrando handlers...")
        register_handlers(bot, bot_handler)

        # Iniciar el bot
        logger.info("Bot completamente configurado y listo para recibir mensajes")
        logger.info("Iniciando infinity_polling...")
        bot.infinity_polling()

    except Exception as e:
        logger.critical(f"ERROR FATAL iniciando el bot: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()
