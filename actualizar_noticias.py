import os
import logging
import requests
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import GetPosts, EditPost
import openai
import re
from datetime import datetime
import pytz
from dotenv import load_dotenv  # Asegúrate de importar load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(filename="proceso_noticias.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configuración de WordPress
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASSWORD = os.getenv("WP_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Configuración de OpenAI
openai.api_key = OPENAI_API_KEY

def generar_palabra_clave(titulo):
    """Genera una palabra clave basada en el título de la noticia usando ChatGPT"""
    prompt = f"""
    Basado en el siguiente título de una noticia sobre perros, proporciona una sola palabra clave relevante para buscar una imagen en Unsplash: {titulo}
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un asistente experto en redacción de artículos SEO."},
                {"role": "user", "content": prompt}
            ]
        )
        palabra_clave = response.choices[0].message['content'].strip()
        logging.info("Palabra clave generada: %s", palabra_clave)
        return palabra_clave
    except Exception as e:
        logging.error("Error al generar palabra clave con ChatGPT: %s", e)
        return "perro"

def buscar_imagen_unsplash(query):
    """Busca una imagen en Unsplash basada en la consulta"""
    url = f"https://api.unsplash.com/search/photos?query={query}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data["results"]:
            return data["results"][0]["urls"]["regular"]
        else:
            logging.warning("No se encontraron imágenes para la consulta: %s", query)
            return ""
    except requests.exceptions.RequestException as e:
        logging.error("Error al buscar imagen en Unsplash: %s", e)
        return ""

def actualizar_noticias():
    """Actualiza las entradas de noticias generadas con imágenes de Unsplash"""
    client = Client(WP_URL, WP_USER, WP_PASSWORD)

    if not os.path.exists("titulos_generados.txt"):
        logging.info("No se encontraron títulos generados. No hay nada que actualizar.")
        return

    try:
        with open("titulos_generados.txt", "r") as file:
            titulos = file.read().splitlines()

        for titulo in titulos:
            palabra_clave = generar_palabra_clave(titulo)
            query = f"perro {palabra_clave}"
            imagen_url = buscar_imagen_unsplash(query)
            if imagen_url:
                posts = client.call(GetPosts({'number': 100, 'post_status': 'publish', 'post_type': 'post'}))
                for post in posts:
                    if post.title == titulo:
                        post.content = f'<img src="{imagen_url}" alt="{titulo}"><br>' + post.content
                        client.call(EditPost(post.id, post))
                        logging.info("Entrada actualizada: %s con imagen: %s", titulo, imagen_url)
    except Exception as e:
        logging.error("Error al actualizar noticias: %s", e)

if __name__ == "__main__":
    actualizar_noticias()