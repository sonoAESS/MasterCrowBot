import hashlib
import os
import fitz
import requests
import numpy as np
from supabase import create_client
from typing import List, Dict, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
import time


class PDFProcessor:
    def __init__(
        self, base_dir: str, hf_api_key: str, supabase_url: str, supabase_key: str
    ):
        self.base_dir = base_dir
        self.supabase = create_client(supabase_url, supabase_key)
        self.hf_api_key = hf_api_key
        self.chunk_size = 1000
        self.overlap = 200

    def process_all_pdfs(self, force_reprocess: bool = False):
        """Procesa todos los PDFs en la estructura de directorios"""
        print("🔄 Procesando archivos PDF...")
        for subject in os.listdir(self.base_dir):
            subject_path = os.path.join(self.base_dir, subject)

            if os.path.isdir(subject_path):
                print(f"📂 Procesando asignatura: {subject}")
                for file in os.listdir(subject_path):
                    if file.endswith(".pdf"):
                        self._process_single_pdf(
                            subject, os.path.join(subject_path, file), force_reprocess
                        )

    def _process_single_pdf(self, subject: str, file_path: str, force_reprocess: bool):
        """Procesa un PDF individual"""
        file_name = os.path.basename(file_path)
        current_hash = self._calculate_file_hash(file_path)

        try:
            # Verificar si el archivo ya fue procesado
            if not force_reprocess and self._already_processed(
                subject, file_name, current_hash
            ):
                print(f"⏩ Saltando archivo ya procesado: {file_name}")
                return

            print(f"📄 Procesando: {file_name}")

            # Eliminar versiones anteriores si existe
            if force_reprocess or self._already_processed(subject, file_name):
                print(f"🔄 Actualizando archivo: {file_name}")
                self.supabase.table("documents").delete().eq("source", file_name).eq(
                    "subject", subject
                ).execute()

            # Procesar nuevo contenido
            doc = fitz.open(file_path)
            chunks = []
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text().strip()
                if text:
                    chunks.extend(self._split_text_with_overlap(text, page_num))

            # Almacenar chunks
            if chunks:
                self._store_chunks(subject, chunks, file_name, current_hash)

        except Exception as e:
            print(f"❌ Error procesando {file_name}: {str(e)}")

    def _split_text_with_overlap(self, text: str, page_num: int) -> List[Dict]:
        """Divide el texto usando el splitter avanzado"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap,
            separators=["\n\n", "\n", r"(?<=\. )", " ", ""],
        )

        chunks = []
        for i, chunk in enumerate(text_splitter.split_text(text)):
            chunks.append(
                {
                    "text": chunk.strip(),
                    "page": page_num,
                    "start_char": i * self.chunk_size,
                    "end_char": (i * self.chunk_size) + len(chunk),
                }
            )
        return chunks

    def _store_chunks(
        self, subject: str, chunks: List[Dict], source: str, file_hash: str
    ):
        """Corregido: Formato correcto para vectores PostgreSQL"""
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self._get_embeddings(texts)

        data = [
            {
                "subject": subject,
                "content": chunk["text"],
                "page": chunk["page"],
                "source": source,
                "file_hash": file_hash,
                # Convertir a formato vector de PostgreSQL
                "embedding": f'[{",".join(map(str, embedding))}]',
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # Insertar en lotes de 100
        for i in range(0, len(data), 100):
            self.supabase.table("documents").insert(data[i : i + 100]).execute()

    def search_context(
        self,
        question: str,
        subject: str,
        folder: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.6,
    ) -> List[Dict]:
        """Búsqueda mejorada con ajuste de parámetros"""
        query_embedding = self._get_embeddings([question])[0]
        
        params = {
            "query_embedding": f'[{",".join(map(str, query_embedding))}]',
            "match_count": top_k * 2,  # Sobremuestreo para filtrado
            "similarity_threshold": similarity_threshold - 0.1,
            "subject_filter": subject,
        }
        try:
            # Añadir esta línea para definir result
            result = self.supabase.rpc("semantic_search", params).execute()
            
            # Filtrado local por carpeta
            if folder:
                result.data = [item for item in result.data if folder in item["source"]]
                
            return [
                {"text": item["content"], "page": item["page"], 
                "source": item["source"], "similarity": item["similarity"]}
                for item in result.data[:top_k]
            ]
            
        except Exception as e:
            print(f"Error en búsqueda semántica: {str(e)}")
            return []

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Obtiene embeddings con reintentos y manejo de errores"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
                    headers={"Authorization": f"Bearer {self.hf_api_key}"},
                    json={"inputs": texts},
                    timeout=30,
                )

                if response.status_code == 200:
                    embeddings = np.array(response.json())
                    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                    return (embeddings / norms).tolist()

                elif response.status_code == 503:
                    print(
                        f"⚠️ Modelo cargando (intento {attempt+1}/{max_retries}), reintentando..."
                    )
                    time.sleep(10 * (attempt + 1))  # Espera exponencial

                else:
                    raise Exception(f"Error en la API: {response.text}")

            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        f"Fallo después de {max_retries} intentos: {str(e)}"
                    )
                time.sleep(5)

        return []  # Fallback seguro

    def _already_processed(
        self, subject: str, source: str, current_hash: str = None
    ) -> bool:
        """Verifica si un archivo ya fue procesado"""
        query = (
            self.supabase.table("documents")
            .select("file_hash")
            .eq("subject", subject)
            .eq("source", source)
            .limit(1)
        )

        if current_hash:
            query.eq("file_hash", current_hash)

        result = query.execute()
        return len(result.data) > 0

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calcula hash SHA-256 del archivo"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                hasher.update(chunk)
        return hasher.hexdigest()

    def list_pdfs(self, folder: str) -> list:
        """Lista los PDFs en la carpeta especificada"""
        target_dir = os.path.join(self.base_dir, folder)
        if not os.path.exists(target_dir):
            return []

        return [
            f
            for f in os.listdir(target_dir)
            if f.endswith(".pdf") and os.path.isfile(os.path.join(target_dir, f))
        ]
