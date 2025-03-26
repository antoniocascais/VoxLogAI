from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MODEL='gemini-2.5-pro-exp-03-25'
API_KEY = os.getenv('GEMINI_API_KEY')  # Get API key from environment variable

if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

PROMPT='Generate a transcript of the speech. Use timestamps in format [8m40s242ms - 8m51s12ms]'

# Initialize client
client = genai.Client(api_key=API_KEY)

# Add retry decorator for the file upload
@retry(
    stop=stop_after_attempt(10),  # Try 3 times
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Wait between attempts

    reraise=True
)
def upload_file(client, filepath):
    try:
        print("Uploading the file...")
        return client.files.upload(file=filepath)
    except Exception as e:
        print(f"Upload attempt failed: {str(e)}")
        raise

# Add retry for content generation
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def generate_content(client, model, contents):
    print("Generating content...")
    return client.models.generate_content(
        model=model,
        contents=contents
    )

try:
    # Upload file with retry
    myfile = upload_file(client, 'sample.mp3')

    # Generate content with retry
    response = generate_content(client, MODEL, [PROMPT, myfile])

    # Save response
    output_filename = f'response_{MODEL}.txt'
    with open(output_filename, 'w', encoding='utf-8') as out_file:
        out_file.write(response.text)

    # Cleanup files
    print('Deleting all files:')
    for f in client.files.list():
        print('Deleting ', f.name)
        client.files.delete(name=f.name)

except Exception as e:
    print(f"An error occurred: {str(e)}")
