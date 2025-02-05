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
            link = articulo.find("a")["href"]
            if link not in historial:
                noticias.append("https://www.eltiempo.com" + link)
        logging.info("Noticias obtenidas: %d", len(noticias))
        return noticias[:5]  # Máximo 5 noticias de las nuevas
    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    prompt = f"Escribe un resumen sobre la siguiente noticia: {noticia}"
    response = openai.client().chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Eres un asistente útil."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def publicar_noticias():
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias()
    for noticia in noticias:
        contenido = generar_contenido_chatgpt(noticia)
        post = WordPressPost()
        post.title = "Resumen de Noticias Caninas"
        post.content = contenido
        post.post_status = "publish"
        client.call(NewPost(post))
        logging.info("Noticia publicada: %s", noticia)

if __name__ == "__main__":
    publicar_noticias()