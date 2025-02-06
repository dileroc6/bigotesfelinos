import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
import openai
import re
import time

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
            if link and "href" in link.attrs:
                noticia_url = "https://www.eltiempo.com" + link["href"]
                if noticia_url not in historial:  # Evitar noticias repetidas
                    noticias.append(noticia_url)

        noticias = noticias[:2]  # Máximo 2 noticias nuevas por ejecución
        guardar_historial(noticias)  # Guardar en historial
        logging.info("Noticias obtenidas: %d", len(noticias))

        return noticias

    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []


def generar_contenido_chatgpt(noticia):
    """Genera contenido optimizado para SEO basado en la noticia usando OpenAI"""
    prompt = f"""
    Escribe un artículo original sobre perros basado en la siguiente noticia: {noticia}
    
    No copies la noticia, sino extrae los puntos clave y explícalos de manera clara. Agrega una reflexión sobre el impacto en la sociedad y dueños de mascotas.
    
    El artículo debe estar en formato HTML, optimizado para SEO, con subtítulos en h2 y h3, párrafos cortos y listas si es necesario.
    
    Finaliza con una invitación a los lectores a compartir sus opiniones.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un experto en redacción SEO."},
                {"role": "user", "content": prompt}
            ]
        )
        contenido = response["choices"][0]["message"]["content"].strip()
        return formatear_encabezados_html(contenido)
    except Exception as e:
        logging.error("Error al generar contenido con OpenAI: %s", e)
        return ""


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
    """Obtiene noticias, genera contenido y lo publica en WordPress"""
    try:
        client = Client(WP_URL, WP_USER, WP_PASSWORD)
    except Exception as e:
        logging.error("Error de conexión con WordPress: %s", e)
        return
    
    noticias = obtener_noticias()
    
    for noticia in noticias:
        contenido = generar_contenido_chatgpt(noticia)
        if not contenido:
            logging.warning("No se generó contenido para la noticia: %s", noticia)
            continue
        
        titulo, contenido_limpio = extraer_titulo_y_limpiar(contenido)
        post = WordPressPost()
        post.title = titulo
        post.content = contenido_limpio
        post.post_status = "publish"
        post.terms_names = {"category": ["Noticias"]}
        
        try:
            client.call(NewPost(post))
            logging.info("Noticia publicada: %s con título: %s", noticia, titulo)
        except Exception as e:
            logging.error("Error al publicar en WordPress: %s", e)
        
        time.sleep(5)  # Evitar sobrecargar el servidor


if __name__ == "__main__":
    publicar_noticias()