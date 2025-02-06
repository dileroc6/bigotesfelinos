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

def obtener_noticias_dia_anterior():
    """Obtiene todas las noticias generadas el día anterior."""
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        noticias = []
        fecha_ayer = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        for articulo in soup.find_all("article"):
            link = articulo.find("a")
            fecha_publicacion = articulo.find("time")
            
            if link and fecha_publicacion:
                noticia_url = "https://www.eltiempo.com" + link["href"]
                noticia_fecha = fecha_publicacion["datetime"].split("T")[0]  # Extrae la fecha en formato YYYY-MM-DD
                
                if noticia_fecha == fecha_ayer:
                    noticias.append(noticia_url)

        logging.info("Noticias obtenidas del día anterior: %d", len(noticias))
        return noticias
    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    """Genera contenido optimizado para SEO basado en la noticia."""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
    Escribe un artículo original sobre perros basado en la siguiente noticia: {noticia}

    No copies la noticia, sino extrae los puntos clave y explícalos de manera clara y accesible para una audiencia interesada en el mundo canino. 
    Aporta valor adicional a los lectores, proporcionando una perspectiva única y profunda, más allá de un simple resumen. 
    
    Estructura el artículo con subtítulos, párrafos breves y listas si es necesario. El artículo debe tener al menos 600 palabras y estar en formato HTML optimizado para SEO.
    
    Si es relevante, incluye un hipervínculo a la fuente de la noticia: <a href='https://www.eltiempo.com/noticias/perros' target='_blank'>El Tiempo</a>.
    """
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un asistente experto en redacción de artículos SEO."},
            {"role": "user", "content": prompt}
        ]
    )
    
    contenido = response.choices[0].message.content.strip()
    return formatear_encabezados_html(contenido)

def formatear_encabezados_html(contenido):
    """Formatea los encabezados h1, h2 y h3 para que tengan la primera letra en mayúscula y el resto en minúscula."""
    return re.sub(r'<h([1-3])>(.*?)</h\1>', lambda m: f'<h{m.group(1)}>{m.group(2).capitalize()}</h{m.group(1)}>', contenido)

def extraer_titulo_y_limpiar(contenido):
    """Extrae el título desde el <h1> generado por ChatGPT y lo elimina del contenido."""
    match = re.search(r'<h1>(.*?)</h1>', contenido, re.IGNORECASE)
    if match:
        titulo = match.group(1).strip()
        contenido_sin_h1 = re.sub(r'<h1>.*?</h1>', '', contenido, count=1, flags=re.IGNORECASE)
        return titulo, contenido_sin_h1.strip()
    return "Noticia sobre perros", contenido

def publicar_noticias():
    """Publica todas las noticias del día anterior en WordPress."""
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias_dia_anterior()

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