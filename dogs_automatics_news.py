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

def obtener_noticias():
    """Obtiene todas las noticias publicadas el día anterior en El Tiempo."""
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        noticias = []
        ayer = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")

        for articulo in soup.find_all("article"):
            fecha_elemento = articulo.find("time")
            if fecha_elemento and ayer in fecha_elemento.text:  # Verifica que la fecha sea de ayer
                link = articulo.find("a")["href"]
                noticia_url = "https://www.eltiempo.com" + link
                noticias.append(noticia_url)

        logging.info("Noticias obtenidas del día anterior: %d", len(noticias))
        return noticias

    except requests.exceptions.RequestException as e:
        logging.error("Error al obtener noticias: %s", e)
        return []

def generar_contenido_chatgpt(noticia):
    """Genera contenido optimizado para SEO basado en la noticia"""
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
    Escribe un artículo original sobre perros basado en la siguiente noticia: {noticia}

    No copies la noticia, sino extrae los puntos clave y explícalos de manera clara y accesible para una audiencia interesada en el mundo canino. Aporta valor adicional a los lectores, proporcionando una perspectiva única y profunda, más allá de un simple resumen. Incluye una reflexión crítica o personal sobre el impacto de la noticia en los dueños de perros, la industria de mascotas o la sociedad en general.

    Adopta un tono informativo pero cercano, como si estuvieras compartiendo la noticia con un amante de los perros. Evita jergas o tecnicismos, asegurándote de que el contenido sea fácil de comprender para cualquier persona, independientemente de su conocimiento sobre el tema.

    Estructura el artículo con subtítulos, párrafos breves y, si es necesario, listas. El artículo debe tener al menos 600 palabras y ser visualmente atractivo, legible y valioso para el lector.

    El artículo debe estar en formato HTML con etiquetas semánticas, optimizado para SEO, y debe integrar palabras clave de manera natural, sin saturar el texto. Finaliza con una reflexión que invite a los lectores a reflexionar sobre el tema o a compartir sus opiniones.

    Los títulos deben ser concisos, llamativos y escritos en minúsculas, excepto la primera letra.

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

    # Asegurarse de que los encabezados h1, h2, h3 tengan la primera letra mayúscula y el resto minúscula
    contenido = formatear_encabezados_html(contenido)
    
    return contenido

def formatear_encabezados_html(contenido):
    """Formatea los encabezados h1, h2 y h3 para que tengan la primera letra en mayúscula y el resto en minúscula."""
    # Usar expresiones regulares para encontrar los encabezados h1, h2 y h3
    contenido = re.sub(r'<h([1-3])>(.*?)</h\1>', lambda m: f'<h{m.group(1)}>{m.group(2).capitalize()}</h{m.group(1)}>', contenido)
    return contenido

def extraer_titulo_y_limpiar(contenido):
    """Extrae el título desde el <h1> generado por ChatGPT y lo elimina del contenido."""
    match = re.search(r'<h1>(.*?)</h1>', contenido, re.IGNORECASE)
    
    if match:
        titulo = match.group(1).strip()  # Extrae el texto dentro de <h1>
        contenido_sin_h1 = re.sub(r'<h1>.*?</h1>', '', contenido, count=1, flags=re.IGNORECASE)  # Elimina el <h1>
        return titulo, contenido_sin_h1.strip()
    
    return "Noticia sobre perros", contenido  # Si no hay <h1>, usa un título genérico

def publicar_noticias():
    """Obtiene noticias, genera contenido y lo publica en WordPress"""
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

if __name__ == "__main__":
    publicar_noticias()