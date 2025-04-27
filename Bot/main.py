import os
from dotenv import load_dotenv
from bot_handler import *

def main():
    load_dotenv()
    
    # Configurar timeouts globales
    application = (
        ApplicationBuilder()
        .token(os.getenv("TOKEN"))
        .connect_timeout(45)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(120)
        .build()
    )

    bot_handler = BotHandler()

    # Nuevos handlers basados en comandos
    handlers = [
        CommandHandler("start", bot_handler.start),
        CommandHandler("ask", bot_handler.handle_general_question),
        CommandHandler("search", bot_handler.handle_embedding_search),
        CallbackQueryHandler(bot_handler.handle_list, pattern="^list_"),
        CallbackQueryHandler(bot_handler.handle_pdf_download, pattern="^download#"),
        CallbackQueryHandler(bot_handler.handle_back, pattern="^back_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.show_help)
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    # Procesar PDFs e iniciar
    bot_handler.pdf_processor.process_all_pdfs()
    application.run_polling()

if __name__ == "__main__":
    main()
