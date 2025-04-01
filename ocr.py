from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get logger
logger = logging.getLogger(__name__)

MODEL = 'gemini-2.5-pro-exp-03-25'
API_KEY = os.getenv('GEMINI_API_KEY')  # Get API key from environment variable

if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

# Initialize client
client = genai.Client(api_key=API_KEY)

# Add retry decorator for content generation
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def generate_content_with_retry(client, model, contents):
    logger.info("Generating content with retry...")
    return client.models.generate_content(
        model=model,
        contents=contents
    )

def ocr_image(image_file):
    """Extract text from an image using OCR
    
    Args:
        image_file: PIL Image object
        
    Returns:
        string: The extracted text
    """
    try:
        logger.info(f"Starting OCR process for image")
        
        # Process the image with Gemini (with retry)
        response = generate_content_with_retry(
            client,
            MODEL,
            ["OCR this image and extract all text content. Format the text to maintain original paragraphs and layout as much as possible.", image_file]
        )
        
        # Get the extracted text
        extracted_text = response.text
        text_preview = extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text
        logger.info(f"OCR successfully generated. Length: {len(extracted_text)} chars. Preview: {text_preview}")
            
        return extracted_text

    except Exception as e:
        logger.error(f"An error occurred during OCR: {str(e)}")
        raise

def ocr_pdf(pdf_content):
    """Extract text from a PDF using OCR
    
    Args:
        pdf_content: PDF file content as bytes
        
    Returns:
        string: The extracted text
    """
    try:
        logger.info(f"Starting OCR process for PDF")
        
        # Process the PDF with Gemini (with retry)
        response = generate_content_with_retry(
            client,
            MODEL,
            [
                types.Part.from_bytes(
                    data=pdf_content,
                    mime_type='application/pdf',
                ),
                "OCR this PDF and extract all text content. Format the text to maintain original paragraphs and layout as much as possible."
            ]
        )
        
        # Get the extracted text
        extracted_text = response.text
        text_preview = extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text
        logger.info(f"OCR successfully generated. Length: {len(extracted_text)} chars. Preview: {text_preview}")
            
        return extracted_text

    except Exception as e:
        logger.error(f"An error occurred during OCR: {str(e)}")
        raise