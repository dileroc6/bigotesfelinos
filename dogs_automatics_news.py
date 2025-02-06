import requests
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuración de URLs y credenciales
NEWS_SOURCES = [
    "https://www.eltiempo.com/noticias/perros",
    "https://www.eltiempo.com/noticias/gatos"
]
WORDPRESS_XMLRPC_URL = "https://tusitio.com/xmlrpc.php"
WORDPRESS_USER = "usuario"
WORDPRESS_PASSWORD = "contraseña"
REWRITE_API_URL = "http://localhost:41343/api"

# Función para obtener noticias de las fuentes
def obtener_noticias():
    noticias = []
    for url in NEWS_SOURCES:
        logging.info(f"Obteniendo noticias de: {url}")
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                if '/noticias/' in link['href'] or '/cultura/' in link['href']:
                    noticia_url = link['href']
                    if noticia_url.startswith('/'):
                        noticia_url = f"https://www.eltiempo.com{noticia_url}"
                    noticias.append(noticia_url)
    logging.info(f"Noticias obtenidas: {len(noticias)}")
    return noticias

# Función para extraer el contenido de una noticia
def extraer_contenido(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        titulo = soup.find('h1').text.strip()
        parrafos = soup.find_all('p')
        contenido = '\n'.join([p.text for p in parrafos])
        return titulo, contenido
    return None, None

# Función para reescribir la noticia
def reescribir_noticia(texto):
    try:
        response = requests.post(REWRITE_API_URL, json={"texto": texto})
        if response.status_code == 200:
            return response.json().get("texto_reescrito", texto)
    except requests.RequestException as e:
        logging.error(f"Error al reescribir la noticia: {e}")
    return texto

# Función para publicar en WordPress
def publicar_en_wordpress(titulo, contenido):
    try:
        response = requests.post(
            WORDPRESS_XMLRPC_URL,
            auth=(WORDPRESS_USER, WORDPRESS_PASSWORD),
            json={"title": titulo, "content": contenido, "status": "publish"}
        )
        if response.status_code == 200:
            logging.info(f"Publicado en WordPress: {titulo}")
        else:
            logging.error(f"Error al publicar en WordPress: {response.text}")
    except requests.RequestException as e:
        logging.error(f"Error al publicar en WordPress: {e}")

# Proceso principal
def main():
    logging.info("Iniciando proceso de extracción y publicación de noticias.")
    noticias = obtener_noticias()
    for url in noticias:
        logging.info(f"Procesando noticia desde: {url}")
        titulo, contenido = extraer_contenido(url)
        if titulo and contenido:
            logging.info("Reescribiendo la noticia...")
            contenido_reescrito = reescribir_noticia(contenido)
            logging.info(f"Publicando en WordPress: {titulo}")
            publicar_en_wordpress(titulo, contenido_reescrito)
            logging.info(f"Noticia procesada y guardada: {url}")
    logging.info("Proceso completado")

if __name__ == "__main__":
    main()