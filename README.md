# VoxLogAI

A simple web-based application for transcribing audio files using Google's Gemini API.

## Features

- Upload audio files (WAV, MP3, AIFF, AAC, OGG, FLAC)
- Transcribe audio using Google's Gemini model
- Privacy-focused (no files are permanently stored)
- Simple, user-friendly interface with a green theme

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Setup

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/VoxLogAI.git
   cd VoxLogAI
   ```

2. Create an environment file:
   ```
   cp .env.example .env
   ```

3. Edit the `.env` file and add your Gemini API key:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Running the Application

Start the application using Docker Compose:

```
docker-compose up -d
```

The application will be available at http://localhost:5000

### Usage

1. Open your web browser and navigate to http://localhost:5000
2. Click "Select File" to choose an audio file
3. Click "Upload" to upload the file
4. Once uploaded, click "Transcribe" to generate a transcript
5. View the transcript in the text box below

## Development

If you want to run the application without Docker:

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```
