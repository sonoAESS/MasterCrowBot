# Proyecto MasterCrow - Asistente Educativo de Bioinformática en Telegram 🤖🧬

Bot educativo especializado en bioinformática que utiliza embeddings y la API de Fireworks para búsquedas inteligentes y análisis de documentos científicos. Creado por el estudiante  de tercer año en Ingniería en Bioinformátca Antonio Elias Sánches Soto de la Universidad de Ciencias Informáticas y el estudiante de segundo año en Ciencias de Datos Alberto Enrique Marichal Fonseca de la Universidad de La Habana.

## Características Principales
- **Comando `/ask`**: Respuestas generales usando modelos de lenguaje
- **Comando `/search`**: Búsqueda semántica usando embeddings de documentos
- **Descarga de documentos** procesados para referencia
- Pipeline de procesamiento de PDFs con OCR (pytesseract + Pillow)
- Integración con Fireworks AI para generación de embeddings

## Dependencias
- python-telegram-bot
- pymupdf
- requests
- python-dotenv
- numpy
- pyesseract
- pillow
- langchain
- scikit-learn
- pyPDF2


## Configuración
1. Obtener API key de [Fireworks AI](https://fireworks.ai)
2. Crear archivo `.env`:
    TOKEN=tu_token_telegram
    FIRE=tu_api_key_fireworks
3. Instalar dependencias:
    pip install -r requirements.txt


## Uso del Bot
| Comando    | Descripción                          | Ejemplo                     |
|------------|--------------------------------------|-----------------------------|
| `/ask`     | Consulta general sobre bioinformática | `/ask Qué es un alineamiento múltiple?` |
| `/search`  | Búsqueda semántica en documentos     | `/search SNPs en genoma humano` |

## Estructura del Proyecto
MASTERCR0W/
├── Bot/
│   ├── data/
│   ├── Libros/
│   ├── logs/
│   ├── .env
│   ├── ai.py
│   ├── bot_handler.py
│   ├── constants.py
│   ├── extract.py
│   ├── logger.py
│   └── main.py
├── logs/
├── .gitignore
├── README.md
└── requirements.txt

## Futuras Implementaciones
- [ ] Integración con SciHub para descarga de papers
- [ ] Módulo de análisis de secuencias con Biopython
- [ ] Búsqueda federada en bases de datos biológicas
- [ ] Visualización de estructuras proteicas

## Contribuir
¡Contribuciones son bienvenidas! Por favor:
1. Haz fork del repositorio
2. Crea una rama con tu feature (`git checkout -b feature/awesome-feature`)
3. Haz commit de tus cambios
4. Push a la rama
5. Abre un Pull Request
