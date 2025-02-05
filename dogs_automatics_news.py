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
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY")) 

    prompt = f"""
    Actúa como un redactor experto en SEO y en contenido sobre mascotas. 
    A partir de la siguiente noticia sobre perros: {noticia}, analiza la información y escribe un artículo original y bien estructurado. 
    No copies la noticia, sino que extrae los puntos clave y explica la información de forma clara para personas interesadas en el mundo canino.

    - Genera un título llamativo y optimizado para SEO, de máximo 60 caracteres.
    - Escribe el contenido en HTML con etiquetas semánticas y optimización para SEO.
    - El artículo debe tener entre 1000 y 1500 palabras.

    Responde en formato JSON con `titulo` y `contenido`.
    """

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "Eres un asistente útil."},
            {"role": "user", "content": prompt}
        ]
    )

    resultado = response.choices[0].message.content.strip()
    
    # Convertir JSON a diccionario
    import json
    data = json.loads(resultado)

    return data["titulo"], data["contenido"]


def publicar_noticias():
    client = Client(WP_URL, WP_USER, WP_PASSWORD)
    noticias = obtener_noticias()
    
    for noticia in noticias:
        titulo, contenido = generar_contenido_chatgpt(noticia)
        
        post = WordPressPost()
        post.title = titulo  # Título generado por ChatGPT
        post.content = contenido
        post.post_status = "publish"
        
        client.call(NewPost(post))
        logging.info("Noticia publicada: %s", titulo)


if __name__ == "__main__":
    publicar_noticias()