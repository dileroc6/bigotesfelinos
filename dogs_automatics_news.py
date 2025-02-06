import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
import openai
import re

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    filename="proceso_noticias.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Configuración de WordPress
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configuración de OpenAI
openai.api_key = OPENAI_API_KEY

# Archivo de historial para evitar noticias repetidas
HISTORIAL_FILE = "historial.txt"

def cargar_historial():
    """Carga el historial de noticias publicadas desde un archivo"""
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as file:
            return set(file.read().splitlines())
    return set()

def guardar_historial(nuevas_noticias):
    """Guarda nuevas noticias en el historial"""
    with open(HISTORIAL_FILE, "a", encoding="utf-8") as file:
        for noticia in nuevas_noticias:
            file.write(noticia + "\n")

def obtener_noticias():
    """Obtiene noticias nuevas de El Tiempo"""
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros", timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        noticias = []
        historial = cargar_historial()

        for articulo in soup.find_all("article"):
            link = articulo.find("a")
            if link:
                noticia_url = "https://www.eltiempo.com" + link["href"]
                if noticia_url not in historial:
                    noticias.append(noticia_url)

        noticias = noticias[:2]
        guardar_historial(noticias)
        logging.info("Noticias obtenidas: %d", len(noticias))
        return noticias

    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    """Genera contenido optimizado para SEO basado en la noticia"""
    try:
        prompt = f"""
        Actúa como un redactor experto en SEO y en contenido sobre mascotas. 
        A partir de la siguiente noticia sobre perros: {noticia}, analiza la información y escribe un artículo original y bien estructurado.
        
        El artículo debe incluir:
        - Una introducción llamativa.
        - Un análisis sobre el impacto en dueños de mascotas.
        - Respuestas a preguntas clave como:
          * ¿Por qué es importante?
          * ¿Cómo afecta a los dueños de perros?
          * ¿Qué acciones pueden tomar?
        
        Usa formato HTML con etiquetas semánticas y optimización SEO.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un asistente experto en redacción de artículos SEO."},
                {"role": "user", "content": prompt}
            ]
        )
        
        contenido = response["choices"][0]["message"]["content"].strip()
        return formatear_encabezados_html(contenido)
    
    except Exception as e:
        logging.error("Error al generar contenido con OpenAI: %s", e)
        return ""

def formatear_encabezados_html(contenido):
    """Corrige los encabezados h1, h2 y h3 para que tengan la primera letra en mayúscula y el resto en minúscula."""
    return re.sub(r"<h([1-3])>(.*?)</h\1>", lambda m: f"<h{m.group(1)}>{m.group(2).capitalize()}</h{m.group(1)}>", contenido)

def extraer_titulo(contenido):
    """Extrae un título llamativo del contenido"""
    for linea in contenido.split("\n")[:5]:
        linea = linea.strip()
        if 20 <= len(linea) <= 80:
            return linea.capitalize()
    return "Noticia sobre perros"

def publicar_noticias():
    """Obtiene noticias, genera contenido y lo publica en WordPress"""
    try:
        client = Client(WP_URL, WP_USER, WP_PASSWORD)
        noticias = obtener_noticias()

        for noticia in noticias:
            contenido = generar_contenido_chatgpt(noticia)
            if not contenido:
                continue
            
            titulo = extraer_titulo(contenido)
            post = WordPressPost()
            post.title = titulo
            post.content = contenido
            post.post_status = "publish"
            post.terms_names = {"category": ["Noticias"]}  # Asegúrate de que la categoría existe

            client.call(NewPost(post))
            logging.info("Noticia publicada: %s con título: %s", noticia, titulo)
    
    except Exception as e:
        logging.error("Error al publicar en WordPress: %s", e)

if __name__ == "__main__":
    publicar_noticias()