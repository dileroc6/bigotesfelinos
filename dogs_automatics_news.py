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
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Crear cliente correctamente

    prompt = f"""
    Actúa como un redactor experto en SEO y en contenido sobre mascotas. 
    A partir de la siguiente noticia sobre perros: {noticia}, analiza la información y escribe un artículo original y bien estructurado. 
    No copies la noticia, sino que extrae los puntos clave y explica la información de forma clara para personas interesadas en el mundo canino.

    El artículo debe incluir:
    - Una introducción que explique la noticia y su relevancia.
    - Un análisis sobre el impacto que puede tener en dueños de mascotas, veterinarios y la industria del cuidado animal.
    - Referencias a estudios o tendencias relacionadas.
    - Respuestas a preguntas clave como: 
        * ¿Por qué esta noticia es importante?
        * ¿Cómo afecta a la vida diaria de los dueños de perros?
        * ¿Qué acciones pueden tomar al respecto?

    Al final, incluye una conclusión con un resumen de los puntos más importantes y recomendaciones prácticas para dueños de perros.

    El artículo debe estar en formato HTML con etiquetas semánticas y optimizado para SEO. 
    La extensión debe ser entre 1000 y 1500 palabras. Usa un tono informativo, profesional y atractivo.
    """
    
    response = client.chat.completions.create(  # Nueva forma de llamar la API
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Eres un asistente útil."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()  # Acceder correctamente al contenido

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