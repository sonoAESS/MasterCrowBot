# constants.py
import os


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


EMBEDDINGS_FILE = os.path.join(ROOT_DIR, "Bot", "data", "embeddings_data.pkl")
INDEX_FILE = os.path.join(ROOT_DIR, "Bot", "data", "vector_index.pkl")
DOCUMENTS_FOLDER = os.path.join(ROOT_DIR, "Bot", "Libros")
LOGS_FOLDER = os.path.join(ROOT_DIR, "Bot", "logs")
