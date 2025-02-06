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

def obtener_noticias():
    """Obtiene todas las noticias publicadas el día anterior en El Tiempo"""
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        noticias = []
        fecha_ayer = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        
        for articulo in soup.find_all("article"):
            fecha_elemento = articulo.find("time")
            if fecha_elemento and fecha_ayer in fecha_elemento.text:
                link = articulo.find("a")["href"]
                noticias.append("https://www.eltiempo.com" + link)
        
        logging.info("Noticias obtenidas del %s: %d", fecha_ayer, len(noticias))
        return noticias
    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    """Genera contenido optimizado para SEO basado en la noticia"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
    Escribe un artículo original sobre perros basado en la siguiente noticia: {noticia}
    
    No copies la noticia, sino extrae los puntos clave y explícalos de manera clara. Aporta valor adicional con una perspectiva única.
    
    Usa subtítulos, párrafos breves y listas si es necesario. El artículo debe tener al menos 600 palabras y estar en HTML optimizado para SEO.
    
    Incluye un hipervínculo a la fuente: <a href='{noticia}' target='_blank'>Fuente</a>.
    """
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un asistente experto en redacción de artículos SEO."},
            {"role": "user", "content": prompt}
        ]
    )
    
    contenido = response.choices[0].message.content.strip()
    return contenido

def extraer_titulo_y_limpiar(contenido):
    """Extrae el título desde el <h1> generado por ChatGPT y lo elimina del contenido."""
    match = re.search(r'<h1>(.*?)</h1>', contenido, re.IGNORECASE)
    if match:
        titulo = match.group(1).strip()
        contenido_sin_h1 = re.sub(r'<h1>.*?</h1>', '', contenido, count=1, flags=re.IGNORECASE)
        return titulo, contenido_sin_h1.strip()
    return "Noticia sobre perros", contenido

def publicar_noticias():
    """Obtiene noticias del día anterior, genera contenido y lo publica en WordPress"""
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias()
    
    for noticia in noticias:
        contenido = generar_contenido_chatgpt(noticia)
        titulo, contenido_limpio = extraer_titulo_y_limpiar(contenido)

        post = WordPressPost()
        post.title = titulo
        post.content = contenido_limpio
        post.post_status = "publish"
        post.terms_names = {"category": ["Noticias"]}
        
        client.call(NewPost(post))
        logging.info("Noticia publicada: %s con título: %s", noticia, titulo)

if __name__ == "__main__":
    publicar_noticias()