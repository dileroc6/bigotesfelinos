import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
import openai
import re
from datetime import datetime, timedelta
import pytz

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(filename="proceso_noticias.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuración de WordPress
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configuración de OpenAI
openai.api_key = OPENAI_API_KEY

# Zona horaria específica
TIMEZONE = pytz.timezone("America/Bogota")  # Cambia esto a la zona horaria que necesites

def obtener_noticias():
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        noticias = []
        ayer = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%d/%m/%Y")
        for articulo in soup.find_all("article"):
            fecha_elemento = articulo.find("time")
            if fecha_elemento and ayer in fecha_elemento.text:  # Verifica que la fecha sea de ayer
                link = articulo.find("a")["href"]
                noticia_url = "https://www.eltiempo.com" + link
                noticias.append(noticia_url)
        logging.info("Noticias obtenidas del día anterior: %d", len(noticias))
        return noticias
    except requests.exceptions.RequestException as e:
        logging.error("Error en la función obtener_noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    try:
        prompt = f"Escribe un resumen sobre la siguiente noticia: {noticia}"
        logging.info("Generando contenido para la noticia: %s", noticia)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente útil."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        contenido = response.choices[0].message['content'].strip()
        logging.info("Contenido generado: %s", contenido)
        return contenido
    except Exception as e:
        logging.error("Error en la función generar_contenido_chatgpt: %s", e)
        return ""

def extraer_titulo_y_limpiar(contenido):
    """Extrae el título del contenido y limpia el <h1>"""
    try:
        match = re.search(r'<h1>(.*?)</h1>', contenido, re.IGNORECASE)
        if match:
            titulo = match.group(1)
            contenido_sin_h1 = re.sub(r'<h1>.*?</h1>', '', contenido, count=1, flags=re.IGNORECASE)  # Elimina el <h1>
            return titulo, contenido_sin_h1.strip()
        return "Noticia sobre perros", contenido  # Si no hay <h1>, usa un título genérico
    except Exception as e:
        logging.error("Error en la función extraer_titulo_y_limpiar: %s", e)
        return "Noticia sobre perros", contenido

def publicar_noticias():
    """Obtiene noticias, genera contenido y lo publica en WordPress"""
    try:
        client = Client(WP_URL, WP_USER, WP_PASSWORD)
        noticias = obtener_noticias()

        for noticia in noticias:
            contenido = generar_contenido_chatgpt(noticia)
            titulo, contenido_limpio = extraer_titulo_y_limpiar(contenido)  # Extrae título y limpia el contenido

            post = WordPressPost()
            post.title = titulo  # Usa el título real extraído del <h1>
            post.content = contenido_limpio  # Usa el contenido sin <h1>
            post.post_status = "publish"
            post.terms_names = {"category": ["Noticias"]}  # Asegúrate de que la categoría existe
            
            client.call(NewPost(post))

            logging.info("Noticia publicada: %s con título: %s", noticia, titulo)
    except Exception as e:
        logging.error("Error en la función publicar_noticias: %s", e)

if __name__ == "__main__":
    publicar_noticias()