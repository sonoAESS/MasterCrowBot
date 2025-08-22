import os
import logging
import time
from telebot import types
from ai_embedding.extract import process_documents, search_similar_chunks_sklearn
from ai_embedding.ai import answer_general_question, embed_question
from constants import DOCUMENTS_FOLDER
from scihub.scihub_handler import handle_scihub_command, process_doi_command

class BotHandler:
    def __init__(self, bot=None):
        """
        Inicializa el manejador del bot con sus dependencias

        Args:
            bot: Instancia de TeleBot pasada desde main.py
        """
        self._init_logging()
        self.bot = bot  # Recibe la instancia del bot desde main.py
        self.processing_users = set()
        print("hola")  # Controla usuarios con procesamiento activo
        self._init_data()

    def _init_logging(self):
        """Configura el logger para esta clase"""
        self.logger = logging.getLogger(__name__)

    def _init_data(self):
        """Inicializa el acceso a los datos procesados"""
        try:
            # Procesamiento de PDFs/vectores realizado solo una vez al inicio
            self.index_model, self.chunks = process_documents()
            if not self.index_model or not self.chunks:
                self.logger.warning("No se pudieron cargar índices o documentos")
        except Exception as e:
            self.logger.error(f"Error inicializando datos: {str(e)}")
            self.index_model = None
            self.chunks = []

    def process_all_pdfs(self):
        """Procesa todos los PDFs para crear embeddings e índices"""
        self.index_model, self.chunks = process_documents()
        return bool(self.index_model and self.chunks)

    def start(self, message_or_call):
        """Maneja el comando start o callback"""
        chat_id = (
            message_or_call.chat.id
            if hasattr(message_or_call, "chat")
            else message_or_call.message.chat.id
        )

        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(
            types.KeyboardButton("🧬 Bioinformática"),
            types.KeyboardButton("💻 Programación"),
        )
        keyboard.add(
            types.KeyboardButton("🔍 Búsqueda"), types.KeyboardButton("❓ Ayuda")
        )
        keyboard.add(types.KeyboardButton("🔗 SciHub"))

        self.bot.send_message(
            chat_id,
            "📚 *Biblioteca Académica*\n"
            "Puedo responder preguntas generales o buscar en documentos.\n\n"
            "• `/ask` - Responde mediante IA\n"
            "• `/search` - Muestra documentos relevantes\n"
            "• Pulsa 🔗 SciHub para instrucciones de descarga de artículos",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    def handle_general_question(self, message):
        """Maneja preguntas generales con la IA - SOLO CON /ask"""
        start_time = time.perf_counter()
        question = message.text.replace("/ask ", "")
        if not question or question == "/ask":
            self.bot.send_message(
                message.chat.id,
                "❌ *Formato correcto:* `/ask [tu pregunta]`",
                parse_mode="Markdown",
            )
            return

        user_id = message.from_user.id
        if user_id in self.processing_users:
            self.bot.send_message(
                message.chat.id,
                "⏳ Ya estoy procesando tu consulta anterior. Por favor espera...",
            )
            return

        self.processing_users.add(user_id)
        self.bot.send_chat_action(message.chat.id, "typing")

        try:
            self.logger.info(f"Generando respuesta general para: {question[:50]}...")
            respuesta = answer_general_question(question)

            # Sanitizar la respuesta para evitar errores de formato
            safe_response = sanitize_markdown(respuesta)

            # Manejar respuestas que podrían dividirse en múltiples mensajes
            if isinstance(safe_response, list):
                for part in safe_response:
                    self.bot.send_message(message.chat.id, part, parse_mode="Markdown")
            else:
                self.bot.send_message(
                    message.chat.id, safe_response, parse_mode="Markdown"
                )

        except Exception as e:
            self.logger.error(f"Error en handle_general_question: {str(e)}")
            self.bot.send_message(
                message.chat.id,
                "❌ No pude generar una respuesta. Por favor, intenta reformular tu pregunta.",
            )
        finally:
            elapsed = time.perf_counter() - start_time
            self.logger.info(
                f"Tiempo de respuesta de handle_general_question: {elapsed:.3f} segundos"
            )
            self.processing_users.remove(user_id)

    def handle_embedding_search(self, message):
        """Busca documentos relevantes y genera respuesta basada en ellos"""
        start_time = time.perf_counter()
        question = message.text.replace("/search ", "")
        if not question or question == "/search":
            self.bot.send_message(
                message.chat.id, "❌ Formato correcto: /search [tu consulta]"
            )
            return

        user_id = message.from_user.id
        if user_id in self.processing_users:
            self.bot.send_message(
                message.chat.id,
                "⏳ Ya estoy procesando tu consulta anterior. Por favor espera...",
            )
            return

        self.processing_users.add(user_id)
        self.bot.send_chat_action(message.chat.id, "typing")

        try:
            self.logger.info(f"Buscando documentos para: {question[:50]}...")

            # Verificación de datos disponibles
            if not self.index_model or not self.chunks:
                self.bot.send_message(
                    message.chat.id,
                    "⚠️ No hay documentos procesados disponibles para búsqueda.",
                )
                return

            # Generación de embedding para la búsqueda
            question_embedding = embed_question(question)
            if not question_embedding:
                self.bot.send_message(
                    message.chat.id,
                    "❌ No pude procesar tu consulta. Intenta con otra pregunta.",
                )
                return

            # Búsqueda semántica de documentos relevantes
            similar_chunks = search_similar_chunks_sklearn(
                question_embedding, self.index_model, self.chunks, top_k=5
            )

            if not similar_chunks:
                self.bot.send_message(
                    message.chat.id,
                    "❓ No encontré documentos relacionados con tu consulta.",
                )
                return

            # Indicar al usuario que estamos generando la respuesta
            self.bot.send_message(
                message.chat.id,
                "⏳ Generando respuesta basada en los documentos relevantes...",
            )

            # Generar respuesta usando los chunks encontrados
            from ai_embedding.ai import generate_answer

            answer, references = generate_answer(question, similar_chunks, self.chunks)

            # Enviar la respuesta principal (dividida si es necesaria)
            if len(answer) > 4000:  # Cambiado de plain_answer a answer
                chunks = [answer[i : i + 4000] for i in range(0, len(answer), 4000)]
                for chunk in chunks:
                    self.bot.send_message(message.chat.id, chunk)
            else:
                self.bot.send_message(
                    message.chat.id, answer
                )  # Cambiado de plain_answer a answer

            # NUEVA IMPLEMENTACIÓN: Manejo mejorado de referencias
            if similar_chunks:
                # Diccionario para agrupar referencias por documento
                doc_refs = {}  # {documento: set(páginas)}

                # Extraer información única de documentos y páginas
                for chunk in similar_chunks:
                    doc_name = chunk.get("document", "")
                    if not doc_name:
                        continue

                    # Convertir a nombre base del documento
                    base_name = os.path.basename(doc_name)
                    pretty_name = base_name.replace(".pdf", "").replace("_", " ")

                    # Extraer páginas únicas
                    pages = chunk.get("pages", [])

                    # Agregar al diccionario, combinando las páginas si ya existe
                    if pretty_name in doc_refs:
                        doc_refs[pretty_name].update(pages)
                    else:
                        doc_refs[pretty_name] = set(pages)

                # Crear mensaje de referencias
                if doc_refs:
                    ref_text = "📚 Referencias consultadas:\n\n"

                    for doc_name, pages in doc_refs.items():
                        # Ordenar páginas para presentación
                        sorted_pages = sorted(pages)
                        pages_str = (
                            ", ".join(map(str, sorted_pages)) if sorted_pages else "N/A"
                        )
                        ref_text += f"• {doc_name} (Pág: {pages_str})\n"

                    # Enviar mensaje con referencias únicas
                    self.bot.send_message(message.chat.id, ref_text)

                    # Crear botones de descarga (solo uno por documento)
                    keyboard = types.InlineKeyboardMarkup()

                    for doc_pretty_name in doc_refs.keys():
                        # Buscar documento en sistema de archivos
                        found = False
                        for pdf_path in self.find_pdf_files(DOCUMENTS_FOLDER):
                            base_name = os.path.basename(pdf_path)
                            pdf_pretty_name = base_name.replace(".pdf", "").replace(
                                "_", " "
                            )

                            if pdf_pretty_name == doc_pretty_name:
                                # Encontramos el documento, crear botón de descarga
                                rel_path = os.path.relpath(pdf_path, DOCUMENTS_FOLDER)
                                keyboard.add(
                                    types.InlineKeyboardButton(
                                        f"📥 Descargar {doc_pretty_name}",
                                        callback_data=f"download#{rel_path}",
                                    )
                                )
                                found = True
                                break

                    # Enviar botones solo si hay documentos para descargar
                    if keyboard.keyboard:
                        self.bot.send_message(
                            message.chat.id,
                            "Selecciona un documento para descargar:",
                            reply_markup=keyboard,
                        )

        except Exception as e:
            self.logger.error(f"Error en handle_embedding_search: {str(e)}")
            self.bot.send_message(message.chat.id, "❌ Error al procesar tu búsqueda.")
        finally:
            elapsed = time.perf_counter() - start_time
            self.logger.info(
                f"Tiempo de respuesta de handle_embedding_search: {elapsed:.3f} segundos"
            )
            self.processing_users.remove(user_id)

    def show_help(self, message_or_call):
        """Muestra ayuda del bot"""
        chat_id = (
            message_or_call.chat.id
            if hasattr(message_or_call, "chat")
            else message_or_call.message.chat.id
        )

        help_text = (
            "🤖 *Comandos disponibles:*\n\n"
            "• `/start` - Inicia el bot\n"
            "• `/ask [pregunta]` - Responde preguntas usando IA\n"
            "• `/search [consulta]` - Responde preguntas usando documentos relevantes\n"
            "• `/help` - Muestra esta ayuda\n\n"
            "Usa `/ask` para preguntas generales y `/search` para encontrar documentos específicos."
        )

        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "🧬 Bioinformática", callback_data="list_bioinformatics"
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "💻 Programación", callback_data="list_programming"
            )
        )

        self.bot.send_message(
            chat_id, help_text, reply_markup=keyboard, parse_mode="Markdown"
        )

    def handle_list(self, call):
        """Maneja listados de documentos por categoría"""
        category = call.data.replace("list_", "")
        chat_id = call.message.chat.id

        # Convertir categorías a nombres de carpetas
        folder_mapping = {
            "BIO": "Bioinformatica",
            "PRO": "Programacion",
        }

        folder = folder_mapping.get(category)
        if not folder:
            self.bot.answer_callback_query(call.id, "Categoría no válida")
            return

        try:
            folder_path = os.path.join(DOCUMENTS_FOLDER, folder)
            if not os.path.exists(folder_path):
                self.bot.send_message(chat_id, f"No se encontró la carpeta {folder}")
                return

            pdf_files = [
                f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")
            ]

            if not pdf_files:
                self.bot.send_message(
                    chat_id, f"No hay documentos disponibles en {folder}"
                )
                return

            keyboard = types.InlineKeyboardMarkup()
            for pdf in pdf_files[:10]:  # Limitamos a 10 resultados
                # Usamos el nombre del archivo como texto del botón y la ruta en el callback
                pretty_name = pdf.replace(".pdf", "").replace("_", " ")
                keyboard.add(
                    types.InlineKeyboardButton(
                        pretty_name, callback_data=f"download#{folder}/{pdf}"
                    )
                )
            keyboard.add(
                types.InlineKeyboardButton("⬅️ Volver", callback_data="back_main")
            )

            self.bot.send_message(
                chat_id,
                f"📚 *Documentos disponibles en {folder}:*",
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
        except Exception as e:
            self.logger.error(f"Error listando PDFs: {e}")
            self.bot.send_message(chat_id, "❌ Error al listar documentos")

    def handle_pdf_download(self, call):
        """Maneja la descarga de documentos PDF"""
        chat_id = call.message.chat.id
        path = call.data.replace("download#", "")

        try:
            file_path = os.path.join(DOCUMENTS_FOLDER, path)
            if not os.path.exists(file_path):
                self.bot.send_message(chat_id, "❌ El archivo solicitado no existe")
                return

            with open(file_path, "rb") as pdf:
                self.bot.send_document(chat_id, pdf)

            self.logger.info(f"Enviado documento: {path}")
        except Exception as e:
            self.logger.error(f"Error enviando PDF: {e}")
            self.bot.send_message(chat_id, "❌ Error al enviar el documento")

    def handle_back(self, call):
        """Maneja botones de regreso"""
        if call.data == "back_main":
            self.show_help(call)
        else:
            self.start(call)

    def handle_message(self, message):
        """Procesa mensajes de texto como consultas y comandos, incluyendo SciHub /doi."""

        text = message.text.strip()
        
        # Si el usuario pulsa el botón de SciHub o escribe /scihub
        if text.lower() == "🔗 scihub" or text.startswith("/scihub"):
            self.logger.info(f"Comando SciHub recibido de usuario {message.from_user.id}: '{text}'")
            handle_scihub_command(self.bot, message)
            return

            # Si el usuario escribe /doi o /scihub seguido de un DOI o URL
        if text.startswith("/doi") or text.startswith("/scihub "):
            self.logger.info(f"Comando DOI/SciHub recibido de usuario {message.from_user.id}: '{text}'")
            process_doi_command(self.bot, message)
            return
        
        # Si el mensaje parece ser un DOI o URL de artículo
        if self._is_probable_doi_or_url(text):
            self.logger.info(f"Detección automática de DOI/URL de usuario {message.from_user.id}: '{text}'")
            process_doi_command(self.bot, message)
            return

        # Responder a mensajes especiales del teclado
        text_lower = text.lower()
        if text_lower in ["🧬 bioinformática", "bioinformática", "bioinformatica"]:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    "Ver documentos", callback_data="list_bioinformatics"
                )
            )
            self.bot.send_message(
                message.chat.id,
                "Selecciona una opción para Bioinformática:",
                reply_markup=keyboard,
            )
            return

        elif text_lower in ["💻 programación", "programación", "programacion"]:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    "Ver documentos", callback_data="list_programming"
                )
            )
            self.bot.send_message(
                message.chat.id,
                "Selecciona una opción para Programación:",
                reply_markup=keyboard,
            )
            return

        elif text_lower in ["🔍 búsqueda", "búsqueda", "busqueda"]:
            self.bot.send_message(
                message.chat.id,
                "Para buscar documentos, usa el comando `/search` seguido de tu consulta.\n"
                "Ejemplo: `/search estructura del ADN`\n\n"
                "Para preguntar a la IA, usa `/ask` seguido de tu pregunta.",
                parse_mode="Markdown",
            )
            return

        elif text_lower in ["❓ ayuda", "ayuda", "help"]:
            self.show_help(message)
            return

        # Mensajes normales: indicar comandos disponibles
        self.bot.send_message(
            message.chat.id,
            "Por favor, especifica qué quieres hacer:\n\n"
            "• `/ask [tu pregunta]` - Para respuesta de IA\n"
            "• `/search [tu consulta]` - Para buscar documentos relevantes\n"
            "• `/doi [DOI]` - Para descargar artículos vía SciHub (ejemplo: `/doi 10.1038/s41586-020-2649-2`)",
            parse_mode="Markdown",
        )

    def _is_probable_doi_or_url(self, text):
            """Detecta si el texto es un DOI o URL de artículo científico"""
            import re
            doi_pattern = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
            url_pattern = r"(https?://[^\s]+)"
            return bool(re.search(doi_pattern, text, re.I) or re.search(url_pattern, text, re.I))

    def find_pdf_files(self, folder_path):
        """
        Busca archivos PDF en una carpeta y sus subcarpetas.

        Args:
            folder_path: Ruta de la carpeta donde buscar archivos PDF.

        Returns:
            Lista de rutas de archivos PDF encontrados.
        """
        pdf_files = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))
        return pdf_files

    def remove_markdown(self, text):
        """
        Elimina completamente el formato Markdown del texto.

        Args:
            text: Texto con posible formato Markdown

        Returns:
            Texto plano sin formato
        """
        import re

        if not text:
            return ""

        # Eliminar bloques de código
        text = re.sub(r"```[\s\S]*?```", "", text)

        # Eliminar formato de negrita y cursiva
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Negrita
        text = re.sub(r"\*(.*?)\*", r"\1", text)  # Cursiva con asteriscos
        text = re.sub(r"_(.*?)_", r"\1", text)  # Cursiva con guiones bajos

        # Eliminar enlaces, manteniendo el texto
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

        # Eliminar formato de listas
        text = re.sub(r"^\s*[-*+]\s", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*\d+\.\s", "", text, flags=re.MULTILINE)

        # Eliminar encabezados
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # Eliminar comillas de código en línea
        text = re.sub(r"`(.*?)`", r"\1", text)

        return text


def sanitize_markdown(text):
    """
    Limpia el texto para evitar errores de formato Markdown en Telegram.

    Args:
        text: Texto a limpiar

    Returns:
        Texto limpio con formato Markdown seguro
    """
    if not text:
        return ""

    # Lista de caracteres especiales de Markdown que pueden causar problemas
    special_chars = [
        "_",
        "*",
        "`",
        "[",
        "]",
        "(",
        ")",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]

    # Escapar los caracteres especiales que no formen parte de un formato válido
    result = ""
    i = 0
    in_code_block = False
    in_bold = False
    in_italic = False
    in_link = False

    while i < len(text):
        char = text[i]

        # Manejo de bloques de código
        if i < len(text) - 2 and text[i : i + 3] == "```":
            in_code_block = not in_code_block
            result += "```"
            i += 3
            continue

        # Si estamos dentro de un bloque de código, añadir sin procesar
        if in_code_block:
            result += char
            i += 1
            continue

        # Manejo de negrita
        if i < len(text) - 1 and text[i : i + 2] == "**":
            in_bold = not in_bold
            result += "*"  # Telegram usa un solo asterisco para negrita
            i += 2
            continue

        # Manejo de cursiva
        if char == "_" or (char == "*" and i < len(text) - 1 and text[i + 1] != "*"):
            in_italic = not in_italic
            result += char
            i += 1
            continue

        # Manejo de enlaces
        if char == "[" and not in_link:
            in_link = True
            result += char
            i += 1
            continue
        elif char == "]" and in_link and i < len(text) - 1 and text[i + 1] == "(":
            in_link = False
            result += char
            i += 1
            continue

        # Escapar caracteres especiales que no son parte de formato
        if char in special_chars and not (in_bold or in_italic or in_link):
            result += "\\"

        result += char
        i += 1

    # Arreglar formatos incompletos
    if in_bold:
        result += "*"
    if in_italic:
        result += "_"
    if in_code_block:
        result += "\n```"

    # Dividir mensajes demasiado largos
    if len(result) > 3500:  # Telegram tiene un límite de 4096, dejamos margen
        parts = []
        current_part = ""
        paragraphs = result.split("\n\n")

        for paragraph in paragraphs:
            if len(current_part) + len(paragraph) + 2 > 3500:
                parts.append(current_part)
                current_part = paragraph
            else:
                if current_part:
                    current_part += "\n\n"
                current_part += paragraph

        if current_part:
            parts.append(current_part)

        return parts

    return result
