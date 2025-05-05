import PyPDF2
from sklearn.neighbors import NearestNeighbors
import numpy as np
import os
import pickle
import time
from typing import List, Dict, Any, Optional, Tuple
from logger import data_logger
from ai_embedding.ai import generate_embeddings, embed_question
from constants import EMBEDDINGS_FILE, INDEX_FILE, DOCUMENTS_FOLDER


def save_data(file_path, data):
    """Guarda datos en formato pickle."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        pickle.dump(data, f)
    data_logger.info(f"Datos guardados en {file_path}")


def load_data(file_path):
    """Carga datos desde un archivo pickle."""
    with open(file_path, "rb") as f:
        data = pickle.load(f)
    data_logger.info(f"Datos cargados desde {file_path}")
    return data


def extract_text_blocks_from_pdf(
    pdf_file, block_size=12500, overlap=500
) -> List[Dict[str, Any]]:
    """
    Extrae bloques de texto de tamaño fijo de un documento PDF.
    Aproximadamente 2500 palabras por bloque (asumiendo promedio de 5 caracteres por palabra)

    Args:
        pdf_file (file object): Archivo PDF abierto en modo binario.
        block_size (int): Tamaño aproximado de cada bloque en caracteres.
        overlap (int): Solapamiento entre bloques para mantener contexto.

    Returns:
        list[dict]: Lista de bloques de texto con metadatos.
    """
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        blocks = []
        full_text = ""
        page_ranges = {}

        # Extraer todo el texto primero y rastrear rangos de páginas
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                start_pos = len(full_text)
                full_text += page_text + "\n\n"
                end_pos = len(full_text)
                page_ranges[page_number] = (start_pos, end_pos)

        # Dividir el texto en bloques superpuestos
        text_length = len(full_text)
        start_positions = list(range(0, text_length, block_size - overlap))

        for i, start_pos in enumerate(start_positions):
            end_pos = min(start_pos + block_size, text_length)
            if end_pos <= start_pos:  # Evitar bloques vacíos al final
                break

            block_text = full_text[start_pos:end_pos]
            if len(block_text.strip()) < 100:  # Ignorar bloques muy pequeños
                continue

            # Determinar en qué páginas aparece este bloque
            block_pages = []
            for page_num, (page_start, page_end) in page_ranges.items():
                # Si hay algún solapamiento entre el bloque y la página
                if not (end_pos < page_start or start_pos > page_end):
                    block_pages.append(page_num)

            # Contar palabras aproximadas (para información)
            word_count = len(block_text.split())

            blocks.append(
                {
                    "chunk_id": f"Block-{i+1}",
                    "section_number": f"B{i+1}",  # Identificador de bloque
                    "header": f"Bloque de texto {i+1} (~{word_count} palabras)",
                    "content": block_text,
                    "text": block_text,
                    "document": pdf_file.name,
                    "pages": block_pages,
                    "type": "text_block",
                    "word_count": word_count,
                }
            )

        data_logger.info(
            f"Se extrajeron {len(blocks)} bloques de texto de {pdf_file.name}"
        )
        return blocks

    except Exception as e:
        data_logger.error(
            f"Error al extraer bloques de texto del documento {pdf_file.name}: {e}"
        )
        raise


def process_documents() -> (
    Tuple[Optional[NearestNeighbors], Optional[List[Dict[str, Any]]]]
):
    """
    Procesa documentos y genera embeddings utilizando bloques de texto fijos.

    Returns:
        Tuple: (modelo de índice, fragmentos procesados)
    """
    start_time = time.time()
    data_logger.info("=== INICIANDO PROCESAMIENTO DE DOCUMENTOS ===")

    if not os.path.exists(DOCUMENTS_FOLDER):
        data_logger.error(
            f"ERROR: Carpeta de documentos no encontrada: {DOCUMENTS_FOLDER}"
        )
        return None, None

    pdf_files = find_pdf_files(DOCUMENTS_FOLDER)
    if not pdf_files:
        data_logger.warning("No se encontraron archivos PDF para procesar.")
        return None, None

    # Cargar datos existentes si están disponibles
    data_logger.info("Verificando datos existentes...")
    existing_chunks, index = load_existing_data()

    if existing_chunks:
        data_logger.info(
            f"Datos cargados: {len(existing_chunks)} chunks existentes en caché"
        )
        # Verificar cuántos chunks ya tienen embeddings
        with_embedding = sum(1 for chunk in existing_chunks if "embedding" in chunk)
        data_logger.info(
            f"Estado de embeddings: {with_embedding}/{len(existing_chunks)} chunks tienen embeddings ({with_embedding/len(existing_chunks)*100:.1f}%)"
        )
    else:
        data_logger.info(
            "No se encontraron datos existentes, comenzando procesamiento desde cero"
        )

    # Procesar nuevos documentos
    data_logger.info(f"Verificando {len(pdf_files)} archivos PDF para procesamiento...")
    new_chunks = get_new_chunks(pdf_files, existing_chunks)

    if new_chunks:
        data_logger.info(
            f"Se encontraron {len(new_chunks)} nuevos fragmentos para procesar"
        )
        data_logger.info("Iniciando generación de embeddings para nuevos fragmentos...")
        embedding_start = time.time()
        generate_embeddings(new_chunks)
        embedding_time = time.time() - embedding_start
        data_logger.info(
            f"Generación de embeddings completada en {embedding_time:.2f} segundos"
        )

        # Actualizar índice con los nuevos fragmentos
        all_chunks = (existing_chunks or []) + new_chunks
        data_logger.info(
            f"Creando índice vectorial con {len(all_chunks)} fragmentos totales..."
        )
        index_start = time.time()
        index, all_chunks = create_vector_store_sklearn(all_chunks)
        index_time = time.time() - index_start
        data_logger.info(f"Índice vectorial creado en {index_time:.2f} segundos")

        # Guardar datos actualizados
        save_start = time.time()
        data_logger.info("Guardando datos procesados en disco...")
        save_data(EMBEDDINGS_FILE, all_chunks)
        save_data(INDEX_FILE, index)
        save_time = time.time() - save_start
        data_logger.info(f"Datos guardados en {save_time:.2f} segundos")

        total_time = time.time() - start_time
        data_logger.info(
            f"=== PROCESAMIENTO COMPLETADO EN {total_time:.2f} SEGUNDOS ==="
        )
        return index, all_chunks

    data_logger.info("No hay nuevos documentos para procesar")
    total_time = time.time() - start_time
    data_logger.info(
        f"=== PROCESAMIENTO COMPLETADO EN {total_time:.2f} SEGUNDOS (SIN CAMBIOS) ==="
    )
    return index, existing_chunks


def get_new_chunks(
    pdf_files: List[str],
    existing_chunks: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Identifica y procesa nuevos documentos no procesados.

    Args:
        pdf_files: Lista de rutas a archivos PDF
        existing_chunks: Fragmentos ya procesados
    """
    start_time = time.time()
    data_logger.info("Iniciando búsqueda de nuevos documentos...")

    # Crear set de documentos ya procesados para búsqueda más eficiente
    processed_docs = set()
    if existing_chunks:
        for chunk in existing_chunks:
            doc_name = chunk.get("document")
            if doc_name:
                base_name = os.path.basename(doc_name)
                processed_docs.add(base_name)
        data_logger.info(
            f"Se encontraron {len(processed_docs)} documentos ya procesados"
        )

    new_chunks = []
    new_docs_count = 0

    # Procesar solo documentos nuevos
    for pdf_path in pdf_files:
        base_name = os.path.basename(pdf_path)
        if base_name in processed_docs:
            data_logger.debug(f"Documento ya procesado (omitido): {base_name}")
            continue

        try:
            new_docs_count += 1
            data_logger.info(
                f"Procesando nuevo documento [{new_docs_count}/{len(pdf_files) - len(processed_docs)}]: {base_name}"
            )
            with open(pdf_path, "rb") as f:
                chunks = extract_text_blocks_from_pdf(f)
                new_chunks.extend(chunks)
                data_logger.info(f"Añadidos {len(chunks)} bloques de {base_name}")
        except Exception as e:
            data_logger.error(f"Error procesando {base_name}: {str(e)}")

    elapsed_time = time.time() - start_time
    data_logger.info(
        f"Procesamiento completado: {len(new_chunks)} nuevos chunks de {new_docs_count} documentos en {elapsed_time:.2f} segundos"
    )
    return new_chunks


def create_vector_store_sklearn(chunks_to_index, new_chunks=None):
    """
    Crea un índice vectorial para búsqueda rápida usando sklearn.

    Args:
        chunks_to_index: Lista completa de fragmentos
        new_chunks: Nuevos fragmentos (parámetro opcional, para compatibilidad)

    Returns:
        Tuple: (modelo de vecinos más cercanos, lista de chunks indexados)
    """
    # Filtrar solo los chunks que tienen embedding
    indexable_chunks = []
    for chunk in chunks_to_index:
        if "embedding" in chunk:
            indexable_chunks.append(chunk)
        else:
            data_logger.warning(
                f"Chunk sin embedding encontrado: {chunk.get('chunk_id', 'desconocido')}"
            )

    if not indexable_chunks:
        data_logger.error("No hay fragmentos con embeddings para indexar")
        return None, chunks_to_index

    # Convertir embeddings a matriz numpy
    embeddings = np.array([chunk["embedding"] for chunk in indexable_chunks])

    # Crear y entrenar modelo de vecinos más cercanos
    data_logger.info(f"Creando índice con {len(indexable_chunks)} vectores")
    try:
        nbrs = NearestNeighbors(
            n_neighbors=min(5, len(indexable_chunks)), algorithm="ball_tree"
        ).fit(embeddings)
        return nbrs, chunks_to_index
    except Exception as e:
        data_logger.error(f"Error creando índice vectorial: {e}")
        return None, chunks_to_index


def search_similar_chunks_sklearn(question, index_model, chunks, top_k=5):
    """
    Busca fragmentos similares a una pregunta usando el índice vectorial.

    Args:
        question: Pregunta o texto de búsqueda (string o embedding)
        index_model: Modelo de vecinos más cercanos
        chunks: Lista completa de fragmentos
        top_k: Número de resultados a retornar

    Returns:
        list: Fragmentos más similares ordenados por relevancia
    """
    if not index_model or not chunks:
        data_logger.warning("Índice o fragmentos no disponibles para búsqueda")
        return []

    # Obtener embedding de la pregunta si es un string
    if isinstance(question, str):
        question_embedding = embed_question(question)
        if not question_embedding:
            data_logger.error("No se pudo generar embedding para la pregunta")
            return []
    else:
        question_embedding = question  # Ya es un embedding

    # Asegurar formato correcto para la búsqueda
    question_embedding = np.array(question_embedding).reshape(1, -1)

    # Realizar búsqueda de vecinos más cercanos
    try:
        # Limitar top_k al número de vecinos del modelo
        actual_k = min(top_k, index_model.n_neighbors)
        distances, indices = index_model.kneighbors(
            question_embedding, n_neighbors=actual_k
        )

        # Extraer resultados
        results = []
        for idx in indices[0]:
            if idx < len(chunks):
                results.append(chunks[idx])

        data_logger.info(f"Búsqueda completada: {len(results)} resultados encontrados")
        return results
    except Exception as e:
        data_logger.error(f"Error en búsqueda: {e}")
        return []


def load_existing_data() -> (
    Tuple[Optional[List[Dict[str, Any]]], Optional[NearestNeighbors]]
):
    """Carga datos existentes de embeddings e índice."""
    try:
        if os.path.exists(EMBEDDINGS_FILE) and os.path.exists(INDEX_FILE):
            data_logger.info("Cargando datos existentes...")
            return load_data(EMBEDDINGS_FILE), load_data(INDEX_FILE)
    except Exception as e:
        data_logger.error(f"Error cargando datos existentes: {e}")

    return None, None


def find_pdf_files(folder: str) -> List[str]:
    """Encuentra archivos PDF en la carpeta especificada y subcarpetas."""
    pdf_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))

    data_logger.info(f"Se encontraron {len(pdf_files)} archivos PDF en {folder}")
    return pdf_files
