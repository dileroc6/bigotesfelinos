import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
import openai

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

# Inicializar historial (puede ser una lista vacía o cargada desde un archivo)
historial = []

def obtener_noticias():
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        noticias = []
        
        for articulo in soup.find_all("article"):
            link_tag = articulo.find("a")
            titulo_tag = articulo.find("h2") or articulo.find("h3")
            
            if link_tag and titulo_tag:
                link = link_tag["href"]
                titulo = titulo_tag.text.strip()
                
                if link not in historial:
                    noticias.append({"titulo": titulo, "link": "https://www.eltiempo.com" + link})

        logging.info("Noticias obtenidas: %d", len(noticias))
        return noticias[:5]  # Máximo 5 noticias nuevas
    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
    actúa como un redactor experto en seo y en contenido sobre mascotas. 
    a partir de la siguiente noticia sobre perros: "{noticia['titulo']}" ({noticia['link']}), analiza la información y escribe un artículo original y bien estructurado. 
    no copies la noticia, sino que extrae los puntos clave y explica la información de forma clara para personas interesadas en el mundo canino.

    el artículo debe:
    - no incluir secciones con títulos como "introducción" o "conclusión"
    - usar títulos en minúsculas
    - estar en formato html con etiquetas semánticas y optimizado para seo
    - tener una extensión entre 1000 y 1500 palabras
    - usar un tono informativo, profesional y atractivo
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "eres un asistente útil."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()

def procesar_texto_html(html):
    """Convierte títulos en minúsculas y elimina secciones como 'introducción' o 'conclusión'."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if tag.text.strip().lower() in ["introducción", "conclusión"]:
            tag.decompose()  # Elimina el título si es 'introducción' o 'conclusión'
        else:
            tag.string = tag.text.lower()  # Convierte a minúsculas

    return str(soup)

def publicar_noticias():
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias()

    for noticia in noticias:
        contenido = generar_contenido_chatgpt(noticia)
        contenido_procesado = procesar_texto_html(contenido)

        post = WordPressPost()
        post.title = noticia["titulo"].lower()  # Asegurar que el título esté en minúsculas
        post.content = contenido_procesado
        post.post_status = "publish"

        client.call(NewPost(post))
        logging.info("Noticia publicada: %s", noticia["titulo"])

if __name__ == "__main__":
    publicar_noticias()