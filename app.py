from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import tempfile
import logging
import sys
from dotenv import load_dotenv
from transcriber import transcribe_audio

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'audio' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Check if file has an allowed extension
    allowed_extensions = {'wav', 'mp3', 'aiff', 'aac', 'ogg', 'flac'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'error': 'Unsupported file format'}), 400

    # Check file size (15MB limit)
    MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB in bytes
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {file.filename}, size: {file_size/1024/1024:.2f}MB")
        return jsonify({'error': f'File too large. Maximum size is 15MB. Your file is {file_size/1024/1024:.2f}MB.'}), 400

    try:
        # Save file to a temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)
        temp_file.close()
        
        logger.info(f"File uploaded successfully: {file.filename}")
        return jsonify({'success': True, 'temp_path': temp_file.name}), 200
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.json
    temp_path = data.get('temp_path')
    
    if not temp_path:
        return jsonify({'error': 'No file path provided'}), 400
    
    try:
        # Get timestamp preference from request
        include_timestamps = data.get('include_timestamps', True)
        logger.info(f"Timestamp preference: {'include' if include_timestamps else 'exclude'}")
        
        # Process the audio file
        transcript = transcribe_audio(temp_path, include_timestamps)
        logger.info(f"File transcribed successfully")
        
        # Delete the temporary file after processing
        try:
            os.unlink(temp_path)
        except Exception as e:
            logger.warning(f"Could not delete temp file: {str(e)}")
        
        return jsonify({'transcript': transcript}), 200
    except Exception as e:
        logger.error(f"Error transcribing file: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
