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
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        noticias = []
        historial = cargar_historial()

        for articulo in soup.find_all("article"):
            link = articulo.find("a")["href"]
            noticia_url = "https://www.eltiempo.com" + link
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
    """Genera contenido optimizado para SEO basado en la noticia"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
    Actúa como un redactor experto en SEO y en contenido sobre mascotas. 
    A partir de la siguiente noticia sobre perros: {noticia}, analiza la información y escribe un artículo original y bien estructurado. 
    No copies la noticia, sino que extrae los puntos clave y explica la información de forma clara para personas interesadas en el mundo canino.

    El artículo debe incluir:
    - Una introducción llamativa sin el título "introducción".
    - Un análisis sobre el impacto en dueños de mascotas, veterinarios y la industria del cuidado animal.
    - Referencias a estudios o tendencias relacionadas.
    - Respuestas a preguntas clave como: 
        * ¿Por qué esta noticia es importante?
        * ¿Cómo afecta a la vida diaria de los dueños de perros?
        * ¿Qué acciones pueden tomar al respecto?

    Al final, incluye una conclusión con un resumen de los puntos más importantes y recomendaciones prácticas para dueños de perros, pero sin el título "conclusión".

    Además, incluye al menos una vez una referencia a la fuente de la noticia de manera natural, con un hipervínculo a: 
    <a href='https://www.eltiempo.com/noticias/perros' target='_blank'>El Tiempo</a>

    El artículo debe estar en formato HTML con etiquetas semánticas y optimizado para SEO. 
    La extensión debe ser entre 1000 y 1500 palabras. Usa un tono informativo, profesional y atractivo.
    Los títulos deben ser cortos y llamativos, en minúsculas excepto la primera letra.
    """
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un asistente experto en redacción de artículos SEO."},
            {"role": "user", "content": prompt}
        ]
    )

    contenido = response.choices[0].message.content.strip()

    # Asegurarse de que los encabezados h1, h2, h3 tengan la primera letra mayúscula y el resto minúscula
    contenido = formatear_encabezados_html(contenido)
    
    return contenido

def formatear_encabezados_html(contenido):
    """Formatea los encabezados h1, h2 y h3 para que tengan la primera letra en mayúscula y el resto en minúscula."""
    # Usar expresiones regulares para encontrar los encabezados h1, h2 y h3
    contenido = re.sub(r'<h([1-3])>(.*?)</h\1>', lambda m: f'<h{m.group(1)}>{m.group(2).capitalize()}</h{m.group(1)}>', contenido)
    return contenido

def extraer_titulo(contenido):
    """Extrae un título llamativo del contenido"""
    primeras_lineas = contenido.split("\n")[:3]  # Tomar las primeras líneas
    for linea in primeras_lineas:
        linea = linea.strip()
        if 20 <= len(linea) <= 80:  # Títulos entre 20 y 80 caracteres
            return linea.capitalize()  # Primera letra en mayúscula, resto en minúscula
    return "Noticia sobre perros"  # Título genérico si no encuentra uno adecuado

def publicar_noticias():
    """Obtiene noticias, genera contenido y lo publica en WordPress"""
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias()

    for noticia in noticias:
        contenido = generar_contenido_chatgpt(noticia)
        titulo = extraer_titulo(contenido)

        post = WordPressPost()
        post.title = titulo
        post.content = contenido
        post.post_status = "publish"
        post.terms = {'category': [157]}  # Especifica la categoría con ID 157
        try:
            client.call(NewPost(post))
            logging.info("Noticia publicada: %s con título: %s", noticia, titulo)
        except Exception as e:
            logging.error("Error al publicar la noticia: %s. Error: %s", noticia, e)

if __name__ == "__main__":
    publicar_noticias()