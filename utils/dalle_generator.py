import openai
import logging
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_dalle_image(prompt: str) -> str:
    """
    Erzeugt ein Bild mit DALL·E basierend auf dem übergebenen Prompt.
    Gibt die URL zum generierten Bild zurück.
    """
    try:
        logging.info(f"🧠 Generiere DALL·E-Bild für Prompt: {prompt}")
        
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="standard"
        )

        image_url = response.data[0].url
        logging.info(f"✅ Bild generiert: {image_url}")
        return image_url

    except Exception as e:
        logging.exception("❌ Fehler bei der DALL·E-Bildgenerierung")
        return None
