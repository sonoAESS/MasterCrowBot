import time
import os
from typing import List, Dict, Any
import requests
from logger import ai_logger
import numpy as np

url = "https://api.fireworks.ai/inference/v1/embeddings"
url_llm = "https://api.fireworks.ai/inference/v1/chat/completions"
headers = {
    "Authorization": f'Bearer fw_3ZbneyZaTFytBHirqLphxtPi', #{os.getenv('FIRE')},
    "Content-Type": "application/json",
}


def generate_embeddings(chunks: List[Dict[str, Any]]) -> None:
    """
    Genera embeddings para los fragmentos de texto que no los tengan

    Args:
        chunks: Lista de fragmentos con metadatos

    Returns:
        None - Modifica los chunks in-place
    """
    ai_logger.info(f"Solicitada generación de embeddings para {len(chunks)} chunks")

    # Contador de embeddings a generar
    total_to_generate = 0
    for chunk in chunks:
        if "embedding" not in chunk:
            total_to_generate += 1

    if total_to_generate == 0:
        ai_logger.info(
            "Todos los chunks ya tienen embeddings. No es necesario generar nuevos."
        )
        return

    ai_logger.info(
        f"Se generarán {total_to_generate} nuevos embeddings (omitiendo {len(chunks) - total_to_generate} existentes)"
    )

    # Generar solo los embeddings faltantes
    generated_count = 0
    start_time = time.time()

    for chunk in chunks:
        #time.sleep(5)
        if "embedding" in chunk:
            continue  # Omitir chunks que ya tienen embedding

        generated_count += 1
        chunk_id = chunk.get("chunk_id", f"Chunk-{generated_count}")
        ai_logger.info(
            f"Generando embedding para fragmento {chunk_id} ({generated_count}/{total_to_generate})"
        )

        try:
            text = chunk.get("text", "")
            if not text:
                ai_logger.warning(
                    f"Fragmento {chunk_id} no tiene texto para embeddings"
                )
                continue

            embedding = embed_question(text)
            if embedding:
                chunk["embedding"] = embedding
                ai_logger.debug(
                    f"Embedding generado correctamente para fragmento {chunk_id}"
                )
            else:
                ai_logger.error(
                    f"No se pudo generar embedding para fragmento {chunk_id}"
                )
        except Exception as e:
            ai_logger.error(
                f"Error generando embedding para fragmento {chunk_id}: {str(e)}"
            )

    elapsed_time = time.time() - start_time
    avg_time = elapsed_time / generated_count if generated_count > 0 else 0

    ai_logger.info(
        f"Generación de embeddings completada: {generated_count} generados en {elapsed_time:.2f} segundos (promedio: {avg_time:.2f} s/embedding)"
    )


def generate_answer(
    question: str,
    context_chunks: List[Dict[str, Any]] | List[List[int]],
    save_chunks: List[Dict[str, Any]] | List[List[int]],
    model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct",
) -> tuple:
    """
    Genera una respuesta citando específicamente artículos, páginas y documentos.

    Args:
        question: Pregunta del usuario
        context_chunks: Fragmentos de artículos relevantes (vectores o diccionarios)
        save_chunks: Todos los chunks disponibles para búsqueda
        model: Modelo generativo a usar

    Returns:
        tuple: (respuesta_formateada, referencias_detalladas)
    """
    try:
        # Procesar los chunks de contexto
        processed_chunks = []
        for chunk in context_chunks:
            if isinstance(chunk, dict):
                processed_chunks.append(chunk)
            else:
                original_chunk = find_original_chunk(chunk, save_chunks)
                if original_chunk:
                    processed_chunks.append(original_chunk)

        if not processed_chunks:
            return (
                "No se encontraron artículos relevantes para responder a tu pregunta.",
                [],
            )

        context_text = ""
        for chunk in processed_chunks:
            doc_name = (
                os.path.basename(chunk["document"])
                .replace(".pdf", "")
                .replace("_", " ")
            )

            pages = ", ".join(map(str, chunk["pages"])) if "pages" in chunk else "N/A"

            context_text += (
                f"\n\n📄 Documento: {doc_name}\n"
                f"📌 Páginas: {pages}\n"
                f"📝 Contenido:\n{chunk['text']}\n"
                "――――――――――――――――――――――"
            )

        # Prompt
        prompt = (
            "Eres un experto en bioinformática y programación. "
            f"PREGUNTA: {question}\n\n"
            "INFORMACIÓN RELEVANTE:\n" + context_text + "\n\n"
            "Basándote en la información anterior y tu conocimiento, "
            "proporciona una respuesta académica completa. "
            "No repitas frases exactas del contexto. "
            "No menciones las fuentes ni que estás usando información proporcionada. "
            "Estructura tu respuesta con encabezados en Markdown cuando sea apropiado.\n\n"
            "RESPUESTA:"
        )

        # Configurar payload para la API
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente legal especializado en interpretar documentos normativos. Responde de manera precisa y profesional.",
                    "name": "system",
                },
                {"role": "user", "content": prompt, "name": "User"},
            ],
            # si lo bajas da mas Precisión
            "temperature": 0.2,  
            "max_tokens": 1500,
            "top_p": 0.9,
        }

        # Generar respuesta
        response = requests.post(url_llm, json=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()

        # Procesar respuesta
        answer = (
            response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )

        # Extraer referencias únicas
        unique_refs = []
        for chunk in processed_chunks:
            doc_name = (
                os.path.basename(chunk["document"])
                .replace(".pdf", "")
                .replace("_", " ")
            )

            pages = ", ".join(map(str, chunk["pages"])) if "pages" in chunk else "N/A"

            ref_str = f"📄 {doc_name} | | 📌 Pág. {pages}"
            unique_refs.append(ref_str)

        answer += "\n\nℹ️ Nota: Siempre verifique la información directamente en los documentos."

        return answer, unique_refs

    except requests.exceptions.RequestException as e:
        ai_logger.error(f"Error en la API: {str(e)}")
        return (
            "⚠️ Error al conectar con el servicio de respuestas. Por favor intenta nuevamente.",
            [],
        )
    except Exception as e:
        ai_logger.error(f"Error generando respuesta: {str(e)}")
        return "⚠️ Error al procesar tu consulta. Por favor intenta nuevamente.", []


def find_original_chunk(vector, chunks_db):
    """
    Función para encontrar el chunk original correspondiente a un vector.
    se Podrá optimizar? par que no sea O(n)?
    """

    closest_chunk = None
    min_distance = float("inf")

    for chunk in chunks_db:
        chunk_vector = chunk.get("embedding")
        if chunk_vector:
            distance = np.linalg.norm(np.array(vector) - np.array(chunk_vector))
            if distance < min_distance:
                min_distance = distance
                closest_chunk = chunk

    return closest_chunk


def embed_question(question: str) -> List[float]:
    """
    Genera embedding para una pregunta

    Args:
        question: Pregunta a convertir en embedding
        model_name: Modelo de embeddings a usar

    Returns:
        List[float]: Embedding generado
    """
    try:
        payload = {
            "input": question,
            "model": "nomic-ai/nomic-embed-text-v1.5",
            "dimensions": 768,
        }
        ai_logger.info(f"Generando embedding para pregunta {question}")
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        question_embedding = response_json["data"][0]["embedding"]
        return question_embedding
    except Exception as e:
        ai_logger.error(f"Error generando embedding para pregunta {question}: {e}")
        return None


def answer_general_question(pregunta: str) -> str:
    """
    Genera una respuesta formal para preguntas generales sin buscar en documentos.

    Args:
        pregunta: La pregunta del usuario

    Returns:
        str: Respuesta formal a la pregunta general
    """
    try:

        prompt = (
            "Como experto en Bioinformática y Programación, responde de manera detallada pero concisa:\n"
            f"Pregunta: {pregunta}\n\n"
            "Incluye cuando sea relevante:\n"
            "- Explicaciones conceptuales\n"
            "- Contexto histórico\n"
            "- Aplicaciones prácticas\n"
            "Respuesta (formato markdown):"
        )

        payload = {
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente especializado en Bioinformática. Responde de manera precisa y profesional.",
                    "name": "system",
                },
                {"role": "user", "content": prompt, "name": "User"},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
            "top_p": 0.9,
        }

        response = requests.post(url_llm, json=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()

        answer = (
            response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        return answer

    except Exception as e:
        return f"⚠️ Error al generar respuesta para tu pregunta general: {str(e)}"
