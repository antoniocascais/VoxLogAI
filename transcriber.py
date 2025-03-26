from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get logger
logger = logging.getLogger(__name__)

MODEL = 'gemini-2.5-pro-exp-03-25'
API_KEY = os.getenv('GEMINI_API_KEY')  # Get API key from environment variable

if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

PROMPT = 'Generate a transcript of the speech. Use timestamps in format [8m40s242ms - 8m51s12ms]'

# Initialize client
client = genai.Client(api_key=API_KEY)

# Add retry decorator for the file upload
@retry(
    stop=stop_after_attempt(10),  # Try 10 times
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Wait between attempts
    reraise=True
)
def upload_file(client, filepath):
    try:
        logger.info("Uploading the file...")
        
        # Determine MIME type based on file extension
        mime_type = "audio/mpeg"  # Default
        file_ext = filepath.lower().split('.')[-1] if '.' in filepath else ''
        
        mime_types = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'aiff': 'audio/aiff',
            'aac': 'audio/aac',
            'ogg': 'audio/ogg',
            'flac': 'audio/flac'
        }
        
        if file_ext in mime_types:
            mime_type = mime_types[file_ext]
            
        logger.info(f"Using MIME type: {mime_type}")
        
        upload_config = {
            "mime_type": mime_type,
        }
        
        return client.files.upload(
                file=filepath,
                config=upload_config
                )
    except Exception as e:
        logger.error(f"Upload attempt failed: {str(e)}")
        raise

# Add retry for content generation
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def generate_content(client, model, contents):
    logger.info("Generating content...")
    return client.models.generate_content(
        model=model,
        contents=contents
    )

def transcribe_audio(filepath):
    """Transcribe audio file
    
    Args:
        filepath: Path to the audio file
        
    Returns:
        string: The transcribed text
    """
    try:
        logger.info(f"Starting transcription process for file at: {filepath}")
        
        # Upload file with retry
        logger.info("Step 1: Uploading file to Gemini API")
        myfile = upload_file(client, filepath)
        logger.info(f"File uploaded successfully to Gemini API with ID: {myfile.name}")

        # Generate content with retry
        logger.info("Step 2: Generating transcript from audio")
        response = generate_content(client, MODEL, [PROMPT, myfile])
        
        # Get the transcribed text
        transcript = response.text
        transcript_preview = transcript[:100] + "..." if len(transcript) > 100 else transcript
        logger.info(f"Transcription successfully generated. Length: {len(transcript)} chars. Preview: {transcript_preview}")
        
        # Cleanup files from Google's servers
        logger.info("Step 3: Cleaning up files from Gemini API")
        delete_count = 0
        for f in client.files.list():
            logger.info(f"Deleting file: {f.name}")
            client.files.delete(name=f.name)
            delete_count += 1
        
        logger.info(f"Cleanup complete. Deleted {delete_count} files from Gemini API.")
        logger.info("Transcription process completed successfully")
            
        return transcript

    except Exception as e:
        logger.error(f"An error occurred during transcription: {str(e)}")
        raise
