import io
import os
import logging
from protein_visual import analyze_pdb, cleanup_files
from federated_search import federated_sparql_query, format_results
import time
from bot_handler import BotHandler

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

    @bot.message_handler(commands=["doi"])
    def doi(message):
        logger.info(
            f"Comando /doi recibido de usuario {message.from_user.id}: '{message.text}'"
        )
        bot_handler.handle_message(message)
    
    # Arreglar
    @bot.message_handler(commands=["federate"])
    def federate(message):
        logger.info(f"Comando /federate recibido de usuario {message.from_user.id}")
        bot.reply_to(message, "Buscando en bases federadas, por favor espera...")
        try:
            results = federated_sparql_query()
            response = format_results(results)
            if not response:
                bot.send_message(message.chat.id, "No se encontraron resultados.")
                return
            # Crear archivo en memoria con la respuesta
            archivo = io.BytesIO()
            archivo.write(response.encode('utf-8'))
            archivo.seek(0)
            # Enviar archivo como documento
            bot.send_document(message.chat.id, archivo, caption="Resultados de la búsqueda federada en TXT")
        except Exception as e:
            logger.error(f"Error en la búsqueda federada: {e}")
            bot.reply_to(message, f"Error en la búsqueda federada: {e}")

    # Callbacks para interacciones con botones
    @bot.callback_query_handler(func=lambda call: call.data.startswith("list_"))
    def callback_list(call):
        logger.info(
            f"Callback list_{call.data[5:]} recibido de usuario {call.from_user.id}"
        )
        bot_handler.handle_list(call)
        
    @bot.message_handler(commands=["visualize"])
    def request_protein(message):
        bot.reply_to(message, "Por favor, envíame el archivo PDB de la estructura proteica.")

    @bot.message_handler(content_types=["document"])
    def handle_protein_file(message):
        if message.document.mime_type != "chemical/x-pdb":
            bot.reply_to(message, "Por favor, envía un archivo PDB válido.")
            return

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_file = "temp.pdb"
        with open(temp_file, "wb") as f:
            f.write(downloaded_file)

        try:
            num_chains, num_residues, sequence = analyze_pdb(temp_file)
            response = (
                f"Estructura analizada:\n"
                f"- Número de cadenas: {num_chains}\n"
                f"- Número total de residuos: {num_residues}\n"
                f"- Secuencia primera cadena (primeros 100 aa): {sequence[:100]}"
            )
            bot.send_message(message.chat.id, response)
            with open("chain_lengths.png", "rb") as img:
                bot.send_photo(message.chat.id, img, caption="Longitud de cadenas")
        except Exception as e:
            logger.error(f"Error analizando PDB: {e}")
            bot.reply_to(message, "Error procesando la estructura. Asegúrate de enviar un archivo PDB válido.")
        finally:
            cleanup_files()
            if os.path.exists(temp_file):
                os.remove(temp_file)

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