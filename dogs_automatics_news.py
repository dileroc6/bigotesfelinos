import requests
import json
import os
import time
import logging
from bs4 import BeautifulSoup
#from unsplash.api import Api
#from unsplash.auth import Auth
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost

# Configuración de logging
logging.basicConfig(filename="proceso_noticias.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuración de WordPress
WP_URL = "bigotescaninos.com/xmlrpc.php"
WP_USER = "userpostnews"
WP_PASSWORD = "0XW9511rB2s)wroKGxGKK2al"

# Configuración de Unsplash (para imágenes gratuitas)
#UNSPLASH_ACCESS_KEY = "tQVn6XF7BdNUv4S14p7ntj5Ett4RJFLlkJgM8t-1ezi0"
#auth = Auth(UNSPLASH_ACCESS_KEY, "", "")
#unsplash_api = Api(auth)

# Archivo para almacenar noticias publicadas
HISTORIAL_FILE = "historial_noticias_dogs.json"

# Cargar historial de noticias
if os.path.exists(HISTORIAL_FILE):
    with open(HISTORIAL_FILE, "r") as f:
        historial = json.load(f)
else:
    historial = []

# Extraer noticias de la web
URL_NOTICIAS = "https://www.eltiempo.com/noticias/perros"
def obtener_noticias():
    logging.info("Obteniendo noticias de: %s", URL_NOTICIAS)
    try:
        response = requests.get(URL_NOTICIAS)
        response.raise_for_status()  # Esto lanzará una excepción si la respuesta no es 200
        soup = BeautifulSoup(response.text, "html.parser")
        noticias = []
        for articulo in soup.find_all("article"):
            link = articulo.find("a")["href"]
            if link not in historial:
                noticias.append("https://www.eltiempo.com" + link)
        logging.info("Noticias obtenidas: %d", len(noticias))
        return noticias[:5]  # Máximo 5 noticias nuevas
    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

# Función para obtener y reescribir noticias con DeepSeek
DEEPSEEK_URL = "http://localhost:41343/api"
def reescribir_noticia(texto):
    logging.info("Reescribiendo la noticia...")
    payload = {"prompt": f"Reescribe este artículo de manera natural y original: {texto}"}
    try:
        response = requests.post(DEEPSEEK_URL, json=payload)
        response.raise_for_status()
        return response.json().get("output", "No se pudo reescribir el artículo.")
    except requests.exceptions.RequestException as e:
        logging.error("Error al reescribir la noticia: %s", e)
        return "No se pudo reescribir el artículo."

# Obtener una imagen de Unsplash (opcional)
#def obtener_imagen():
#    fotos = unsplash_api.search.photos("perros", per_page=1)
#    return fotos[0].urls.full if fotos else ""

# Publicar en WordPress
def publicar_en_wordpress(titulo, contenido, imagen):
    logging.info("Publicando en WordPress: %s", titulo)
    try:
        wp = Client(WP_URL, WP_USER, WP_PASSWORD)
        post = WordPressPost()
        post.title = titulo
        post.content = f'<img src="{imagen}"/><br>{contenido}'
        post.post_status = "publish"
        wp.call(NewPost(post))
        logging.info("Publicado: %s", titulo)
    except Exception as e:
        logging.error("Error al publicar en WordPress: %s", e)

# Ejecutar el proceso
def ejecutar():
    logging.info("Iniciando proceso de extracción y publicación de noticias.")
    noticias = obtener_noticias()
    logging.info("Noticias obtenidas: %d", len(noticias))
    if noticias:
        for url in noticias:
            logging.info("Procesando noticia desde: %s", url)
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                titulo = soup.find("h1").text
                contenido_original = " ".join([p.text for p in soup.find_all("p")])
                contenido_reescrito = reescribir_noticia(contenido_original)
                #imagen = obtener_imagen()
                publicar_en_wordpress(titulo, contenido_reescrito, "")
                historial.append(url)
                with open(HISTORIAL_FILE, "w") as f:
                    json.dump(historial, f)
                logging.info("Noticia procesada y guardada: %s", url)
            else:
                logging.error("Error al acceder a la noticia: %s", url)
    else:
        logging.error("No se obtuvieron noticias.")
    logging.info("Proceso completado")

# Ejecutar cada 12 horas (descomentando la siguiente parte si deseas ejecutarlo de forma cíclica)
if __name__ == "__main__":
    ejecutar()
    #while True:
    #    ejecutar()
    #    time.sleep(43200)  # 12 horas