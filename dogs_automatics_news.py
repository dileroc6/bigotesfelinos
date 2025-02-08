import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost, GetPosts, EditPost
import openai
import re
from datetime import datetime, timedelta
import pytz

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

# Zona horaria específica
TIMEZONE = pytz.timezone("America/Bogota")  # Cambia esto a la zona horaria que necesites

def obtener_noticias():
    """Obtiene noticias nuevas de El Tiempo"""
    try:
        response = requests.get("https://www.eltiempo.com/noticias/perros")
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        noticias = []
        ayer = (datetime.now(TIMEZONE) - timedelta(days=1)).strftime("%d/%m/%Y")
        logging.info("Fecha de ayer: %s", ayer)
        
        for articulo in soup.find_all("article"):
            fecha_elemento = articulo.find("time")
            if fecha_elemento:
                fecha_texto = fecha_elemento.text.strip().lower()
                logging.info("Fecha del artículo: %s", fecha_texto)
                # Extraer la fecha del texto del artículo
                match = re.search(r'(\d{1,2})\s+([a-z]+)\s+de\s+(\d{4})', fecha_texto)
                if match:
                    dia, mes, año = match.groups()
                    # Convertir el mes a número
                    meses = {
                        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                    }
                    mes_numero = meses.get(mes)
                    fecha_articulo = f"{dia.zfill(2)}/{mes_numero}/{año}"
                    logging.info("Fecha del artículo formateada: %s", fecha_articulo)
                    if fecha_articulo == ayer:  # Verifica que la fecha sea de ayer
                        link = articulo.find("a")["href"]
                        noticia_url = "https://www.eltiempo.com" + link
                        noticias.append(noticia_url)

        noticias = noticias[:2]  # Máximo 2 noticias nuevas por ejecución
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
            {"role": "system", "content": "Eres un asistente experto en redacción de artículos SEO y conocedor de todo lo relacionado con perros."},
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

def publicar_noticias():
    """Obtiene noticias, genera contenido y lo publica en WordPress"""
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias()
    if not noticias:
        logging.info("No se encontraron noticias del día anterior.")
        return

    titulos_generados = []

    for noticia in noticias:
        contenido = generar_contenido_chatgpt(noticia)
        titulo, contenido_limpio = extraer_titulo_y_limpiar(contenido)  # Extrae título y limpia el contenido
        titulos_generados.append(titulo)

        post = WordPressPost()
        post.title = titulo  # Usa el título real extraído del <h1>
        post.content = contenido_limpio  # Usa el contenido sin <h1>
        post.post_status = "publish"
        post.terms_names = {"category": ["Noticias"]}  # Asegúrate de que la categoría existe
        
        client.call(NewPost(post))

        logging.info("Noticia publicada: %s con título: %s", noticia, titulo)

    # Guardar los títulos generados en un archivo
    with open("titulos_generados.txt", "w") as file:
        for titulo in titulos_generados:
            file.write(titulo + "\n")

    # Actualizar entradas con imágenes de Unsplash
    actualizar_noticias(client, titulos_generados)

def actualizar_noticias(client, titulos):
    """Actualiza las entradas de noticias generadas con imágenes de Unsplash"""
    try:
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
    publicar_noticias()