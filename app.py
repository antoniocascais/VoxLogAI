from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import tempfile
import logging
import sys
import re
import yt_dlp
import uuid
import time
import PIL.Image
from dotenv import load_dotenv
from transcriber import transcribe_audio
from ocr import ocr_image, ocr_pdf

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Dictionary to store mapping between file_id and actual file path
# Format: {file_id: {"path": file_path, "timestamp": creation_time}}
temp_file_map = {}

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
        
        # Generate a secure unique ID for this file
        file_id = str(uuid.uuid4())
        
        # Store the mapping between ID and actual path
        temp_file_map[file_id] = {
            "path": temp_file.name, 
            "timestamp": time.time()
        }
        
        # Clean up old temp files
        cleanup_temp_files()
        
        logger.info(f"File uploaded successfully: {file.filename}, assigned ID: {file_id}")
        return jsonify({'success': True, 'file_id': file_id}), 200
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Function to clean up old temporary files
def cleanup_temp_files():
    """Remove mapping entries older than 30 minutes and delete their associated files"""
    current_time = time.time()
    expired_time = current_time - (30 * 60)  # 30 minutes in seconds
    
    # Find expired entries
    expired_ids = [file_id for file_id, data in temp_file_map.items() 
                if data["timestamp"] < expired_time]
    
    # Delete expired files and remove from map
    for file_id in expired_ids:
        try:
            file_path = temp_file_map[file_id]["path"]
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Deleted expired temp file: {file_path}")
            del temp_file_map[file_id]
            logger.info(f"Removed expired file_id: {file_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up file_id {file_id}: {str(e)}")

@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.json
    file_id = data.get('file_id')
    
    if not file_id:
        return jsonify({'error': 'No file ID provided'}), 400
    
    # Look up the actual file path using the provided ID
    if file_id not in temp_file_map:
        return jsonify({'error': 'Invalid or expired file ID'}), 400
    
    temp_path = temp_file_map[file_id]["path"]
    
    # Validate that the temporary path is within the expected temporary directory
    expected_temp_dir = tempfile.gettempdir()
    if not os.path.abspath(temp_path).startswith(os.path.abspath(expected_temp_dir)):
        logger.error(f"Security violation: temp_path {temp_path} is outside of expected temp directory {expected_temp_dir}")
        return jsonify({'error': 'Security violation detected'}), 400
    
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
            # Remove from our mapping after successful processing
            del temp_file_map[file_id]
            logger.info(f"Deleted temp file and removed mapping for {file_id}")
        except Exception as e:
            logger.warning(f"Could not delete temp file: {str(e)}")
        
        return jsonify({'transcript': transcript}), 200
    except Exception as e:
        logger.error(f"Error transcribing file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe_youtube', methods=['POST'])
def transcribe_youtube():
    data = request.json
    youtube_url = data.get('youtube_url')
    
    if not youtube_url:
        return jsonify({'error': 'No YouTube URL provided'}), 400
    
    # Validate YouTube URL
    youtube_pattern = r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]{11}.*$'
    if not re.match(youtube_pattern, youtube_url):
        return jsonify({'error': 'Invalid YouTube URL format'}), 400
    
    try:
        # Get timestamp preference from request
        include_timestamps = data.get('include_timestamps', True)
        logger.info(f"Timestamp preference: {'include' if include_timestamps else 'exclude'}")
        
        # Download audio from YouTube
        logger.info(f"Downloading audio from YouTube: {youtube_url}")
        
        # Create a temporary directory for the download
        temp_dir = tempfile.mkdtemp()
        
        # Simplified approach - create a more predictable output file
        output_template = os.path.join(temp_dir, 'audio.mp3')
        
        # Define options for yt-dlp - simple approach without ffmpeg dependency
        ydl_opts = {
            # Extract audio only - use a format that doesn't need conversion
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
            # Fixed output name to avoid path issues
            'outtmpl': os.path.join(temp_dir, 'audio.%(ext)s'),
            # No post-processing to avoid ffmpeg dependency
            # 'postprocessors': [],
            'writethumbnail': False,
            'noplaylist': True,
        }
        
        # Download the video and extract audio
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=True)
                video_title = info_dict.get('title', 'Unknown Title')
                logger.info(f"Downloaded and extracted audio from: {video_title}")
        except Exception as e:
            logger.error(f"Error during YouTube download: {str(e)}")
            raise
        
        # Find any audio file in the temp directory
        logger.info(f"Searching for downloaded audio files in: {temp_dir}")
        files = os.listdir(temp_dir)
        logger.info(f"Files in directory: {files}")
        
        if not files:
            raise Exception("No files found after YouTube download")
        
        # Check for common audio extensions first
        for ext in ['.m4a', '.mp3', '.webm', '.opus', '.ogg']:
            for file in files:
                if file.endswith(ext):
                    final_temp_path = os.path.join(temp_dir, file)
                    logger.info(f"Found audio file with {ext} extension: {final_temp_path}")
                    break
            if 'final_temp_path' in locals():
                break
        
        # If no audio file with known extension, just use the first file
        if 'final_temp_path' not in locals():
            final_temp_path = os.path.join(temp_dir, files[0])
            logger.info(f"No known audio format found, using first file: {final_temp_path}")
        
        # Process the audio file
        logger.info(f"Transcribing YouTube audio: {video_title}")
        transcript = transcribe_audio(final_temp_path, include_timestamps)
        logger.info(f"YouTube audio transcribed successfully: {video_title}")
        
        # Delete the temporary files after processing
        try:
            # Remove the temp file we used
            if os.path.exists(final_temp_path):
                os.unlink(final_temp_path)
                logger.info(f"Deleted temp file: {final_temp_path}")
            
            # Clean up any other files in the temp directory
            for f in os.listdir(temp_dir):
                try:
                    file_path = os.path.join(temp_dir, f)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        logger.info(f"Deleted additional temp file: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {f}: {str(e)}")
            
            # Remove the temp directory
            os.rmdir(temp_dir)
            logger.info(f"Deleted temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Could not delete all temp files: {str(e)}")
        
        return jsonify({'transcript': transcript, 'title': video_title}), 200
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"YouTube download error: {str(e)}")
        return jsonify({'error': f'Error downloading YouTube video: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error transcribing YouTube audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

# OCR Image processing
@app.route('/ocr_image', methods=['POST'])
def process_image_ocr():
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Check if file has an allowed extension
    allowed_extensions = {'jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'error': 'Unsupported file format'}), 400

    # Check file size (20MB limit)
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB in bytes
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {file.filename}, size: {file_size/1024/1024:.2f}MB")
        return jsonify({'error': f'File too large. Maximum size is 20MB. Your file is {file_size/1024/1024:.2f}MB.'}), 400

    try:
        # Process the image
        image = PIL.Image.open(file)
        logger.info(f"Image loaded successfully: {file.filename}")
        
        # Process the image with OCR
        extracted_text = ocr_image(image)
        logger.info(f"OCR processing complete for image: {file.filename}")
        
        return jsonify({'text': extracted_text}), 200
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return jsonify({'error': str(e)}), 500

# OCR PDF processing
@app.route('/ocr_pdf', methods=['POST'])
def process_pdf_ocr():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Check if file has an allowed extension
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() != 'pdf':
        return jsonify({'error': 'Unsupported file format. Only PDF files are allowed.'}), 400

    # Check file size (20MB limit)
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB in bytes
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        logger.warning(f"File too large: {file.filename}, size: {file_size/1024/1024:.2f}MB")
        return jsonify({'error': f'File too large. Maximum size is 20MB. Your file is {file_size/1024/1024:.2f}MB.'}), 400

    try:
        # Read the PDF content
        pdf_content = file.read()
        logger.info(f"PDF loaded successfully: {file.filename}")
        
        # Process the PDF with OCR
        extracted_text = ocr_pdf(pdf_content)
        logger.info(f"OCR processing complete for PDF: {file.filename}")
        
        return jsonify({'text': extracted_text}), 200
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
