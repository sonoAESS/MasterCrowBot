import requests
import time

import requests
from typing import List

class AcademicAssistant:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.general_knowledge_model = "google/flan-t5-xxl"
        self.academic_model = "google/flan-t5-xxl"

    def generate_general_answer(self, question: str) -> str:
        """Genera respuestas usando conocimiento general"""
        prompt = (
            "Como experto en Bioinformática y Programación, responde de manera detallada pero concisa:\n"
            f"Pregunta: {question}\n\n"
            "Incluye cuando sea relevante:\n"
            "- Explicaciones conceptuales\n"
            "- Contexto histórico\n"
            "- Aplicaciones prácticas\n"
            "Respuesta (formato markdown):"
        )
        return self._call_hf_api(prompt, model=self.general_knowledge_model)

    def generate_academic_answer(self, question: str, context_chunks: List[dict]) -> str:
        """Combina contexto y conocimiento general"""
        context_text = "\n".join([chunk['text'] for chunk in context_chunks])
        
        prompt = (
            "Integra esta información con tu conocimiento profesional:\n"
            f"Contexto:\n{context_text}\n\n"
            f"Pregunta: {question}\n\n"
            "Instrucciones:\n"
            "1. Si el contexto es relevante, úsalo como base\n"
            "2. Si es insuficiente, complementa con conocimiento general\n"
            "3. Estructura la respuesta en secciones claras\n"
            "Respuesta (markdown):"
        )
        return self._call_hf_api(prompt, model=self.academic_model)

    def _call_hf_api(self, prompt: str, model: str, max_length: int = 800) -> str:
        """API mejorada con manejo de modelos y errores"""
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_length": max_length,
                        "temperature": 0.5,
                        "do_sample": True,
                        "top_k": 50
                    }
                },
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()[0]['generated_text']
            return f"🔍 Error en la API: {response.text}"
            
        except requests.exceptions.Timeout:
            return "⏳ Tiempo excedido procesando la solicitud"
        except Exception as e:
            return f"⚠️ Error de conexión: {str(e)}"


    def evaluate_triviality(self, question: str) -> bool:
        """Evalúa si la pregunta es trivial/común"""
        prompt = (
            "Clasifica la pregunta como 'True' (trivial) o 'False' (académica):\n"
            "Ejemplos:\n"
            "'Hola' → True\n"
            "'Explica la fotosíntesis' → False\n"
            f"Pregunta: {question}\nRespuesta:"
        )
        response = self._call_hf_api(prompt, max_length=20)
        return "true" in response.lower()

    def generate_friendly_response(self, message: str) -> str:
        """Respuesta amable para preguntas no académicas"""
        prompt = (
            "Eres un asistente académico amable. Responde brevemente:\n"
            f"Usuario dice: {message}\n"
            "Respuesta (1-2 líneas, formato natural):"
        )
        return self._call_hf_api(prompt)

    def _call_hf_api(self, prompt: str, max_length: int = 500) -> str:
        """Llama a la API con reintentos y timeouts controlados"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://api-inference.huggingface.co/models/google/flan-t5-xxl",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_length": max_length,
                            "temperature": 0.3,
                            "do_sample": True
                        }
                    },
                    timeout=10  # Reducir timeout de API
                )
                
                if response.status_code == 200:
                    return response.json()[0]['generated_text']
                    
                # Manejo específico de errores HTTP
                return f"Error en API (Código {response.status_code}): {response.text}"
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt == max_retries - 1:
                    return "Error de conexión: Tiempo excedido"
                time.sleep(2 ** attempt)  # Espera exponencial
                
            except Exception as e:
                return f"Error inesperado: {str(e)}"

