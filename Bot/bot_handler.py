import os
import logging
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
from telegram.error import TimedOut, BadRequest
from data_processor import PDFProcessor
from ai_integration import AcademicAssistant


class BotHandler:
    def __init__(self):
        self._init_logging()
        self._init_services()

    def _init_logging(self):
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        self.logger = logging.getLogger(__name__)

    def _init_services(self):
        self.pdf_processor = PDFProcessor(
            base_dir="Libros",
            hf_api_key=os.getenv("HF_API_KEY"),
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
        )
        self.academic_bot = AcademicAssistant(os.getenv("HF_API_KEY"))

    async def _send_adaptive_response(self, update: Update, respuesta: str):
        """Envía respuestas largas en partes"""
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🧬 Bioinformática", callback_data="list_bio")],
                [InlineKeyboardButton("💻 Programación", callback_data="list_prog")],
            ]
        )

        if len(respuesta) > 4000:
            parts = [respuesta[i : i + 4000] for i in range(0, len(respuesta), 4000)]
            for part in parts[:-1]:
                await update.message.reply_text(part, parse_mode="Markdown")
            await update.message.reply_text(
                parts[-1], reply_markup=keyboard, parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                respuesta, reply_markup=keyboard, parse_mode="Markdown"
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menú principal con manejo de timeout mejorado"""
        try:
            keyboard = [
                [InlineKeyboardButton("🧬 Bioinformática", callback_data="list_bio")],
                [InlineKeyboardButton("💻 Programación", callback_data="list_prog")]
            ]
            
            # Mensaje simplificado para evitar timeout
            await update.message.reply_text(
                "📚 *Biblioteca Académica*\nElige una categoría:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
                write_timeout=30,
                connect_timeout=30
            )
        except TimedOut:
            self.logger.warning("Timeout en comando /start")
            await update.message.reply_text("⌛ Sistema ocupado, intenta nuevamente")


    async def handle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja la selección de PDFs"""
        query = update.callback_query
        try:
            # Verificar timeout
            if (time.time() - query.message.date.timestamp()) > 45:
                await self._safe_answer_query(
                    query, "⚠️ La operación expiró, usa el menú actual", show_alert=True
                )
                return

            await self._safe_answer_query(query)
            folder_map = {
                "list_bio": ("BIO", "Bioinformática"),
                "list_prog": ("PRO", "Programación"),
            }
            folder, subject = folder_map[query.data]
            pdfs = self.pdf_processor.list_pdfs(folder)

            if not pdfs:
                await query.edit_message_text(
                    f"📂 *{subject}*\nNo hay PDFs disponibles."
                )
                return

            # Construir lista de botones
            pdf_buttons = [
                [
                    InlineKeyboardButton(
                        pdf, callback_data=f"download#{folder}#{pdf.replace('_', '∣')}"
                    )
                ]
                for pdf in pdfs
            ]
            pdf_buttons.append(
                [InlineKeyboardButton("↩️ Volver", callback_data="back_main")]
            )

            await query.edit_message_text(
                f"📂 *{subject}*\nSelecciona un PDF:",
                reply_markup=InlineKeyboardMarkup(pdf_buttons),
                parse_mode="Markdown",
            )

        except Exception as e:
            self.logger.error(f"Error en handle_list: {str(e)}")
            await self._safe_answer_query(
                query, "❌ Error al cargar documentos", show_alert=True
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejo mejorado de mensajes con cascada de respuestas"""
        await update.message.reply_chat_action("typing")
        
        try:
            # Búsqueda semántica mejorada
            context_chunks = self.pdf_processor.search_context(
                question=update.message.text,
                subject="",
                folder="",
                similarity_threshold=0.6,
                top_k=5
            )
            
            # Sistema de cascada inteligente
            if context_chunks:
                answer = self.academic_bot.generate_academic_answer(
                    question=update.message.text,
                    context_chunks=context_chunks
                )
            else:
                answer = self.academic_bot.generate_general_answer(update.message.text)
            
            # Formateo adaptativo
            await self._send_adaptive_response(update, answer)
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            fallback = (
                "⚠️ Sistema sobrecargado. Respuesta general:\n\n" +
                self.academic_bot.generate_general_answer(update.message.text)
            )
            await update.message.reply_text(fallback)

    async def _safe_answer_query(self, query, text=None, show_alert=False):
        """Manejo seguro de respuestas a queries"""
        try:
            await query.answer(text=text, show_alert=show_alert, timeout=10)
        except BadRequest as e:
            if "query id is invalid" in str(e):
                self.logger.warning(f"Query expirada: {query.data}")
            else:
                self.logger.error(f"Error en query: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error genérico en query: {str(e)}")

    async def handle_pdf_download(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Envía el PDF seleccionado"""
        query = update.callback_query
        try:
            _, folder, encoded_filename = query.data.split("#", 2)
            filename = encoded_filename.replace("∣", "_")
            file_path = os.path.join("Libros", folder, filename)

            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=open(file_path, "rb"),
                filename=filename,
            )

        except Exception as e:
            self.logger.error(f"Error enviando PDF: {str(e)}")
            await query.answer("❌ Error al enviar el PDF")

    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Vuelve al menú principal"""
        query = update.callback_query
        await query.answer()
        simulated_update = Update(update.update_id, message=query.message)
        await self.start(simulated_update, context)

    async def handle_general_question(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Maneja /ask [pregunta]"""
        question = " ".join(context.args)
        if not question:
            await update.message.reply_text("❌ Formato correcto: /ask [tu pregunta]")
            return

        await update.message.reply_chat_action("typing")
        try:
            respuesta = self.academic_bot.generate_general_answer(question)
            await self._send_adaptive_response(update, respuesta)
        except Exception as e:
            await self._handle_error(update, e)

    async def handle_embedding_search(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Maneja /search [pregunta]"""
        question = " ".join(context.args)
        if not question:
            await update.message.reply_text(
                "❌ Formato correcto: /search [tu consulta]"
            )
            return

        await update.message.reply_chat_action("typing")
        try:
            context_chunks = self.pdf_processor.search_context(
                question=question, subject="", folder="", similarity_threshold=0.65
            )

            if context_chunks:
                respuesta = self.academic_bot.generate_academic_answer(
                    question, context_chunks
                )
            else:
                respuesta = (
                    "🔍 No se encontraron coincidencias en los documentos.\n\n"
                    + self.academic_bot.generate_general_answer(question)
                )

            await self._send_adaptive_response(update, respuesta)
        except Exception as e:
            await self._handle_error(update, e)

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra ayuda para comandos no reconocidos"""
        await update.message.reply_text(
            "ℹ️ Comandos disponibles:\n\n"
            "*/ask* [pregunta] - Consulta general\n"
            "*/search* [consulta] - Búsqueda en documentos\n"
            "*/start* - Menú principal",
            parse_mode="Markdown"
        )

    async def _handle_error(self, update: Update, error: Exception):
        """Manejo centralizado de errores"""
        self.logger.error(f"Error: {str(error)}")
        error_message = (
            "⚠️ Error procesando tu solicitud. Intenta:\n"
            "- Reformular tu pregunta\n"
            "- Verificar la ortografía\n"
            "- Usar comandos específicos (/ask o /search)"
        )
        await update.message.reply_text(error_message)