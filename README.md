# AI Video Tool - OpenAI DALL-E Edition

A Python application for generating AI images from scripts and creating videos with voiceovers using OpenAI's DALL-E 3 API.

## Features

- **AI Image Generation**: Create images from text scripts using OpenAI DALL-E 3
- **Video Processing**: Convert images to video clips with timestamps
- **B-Roll Reorganization**: Shuffle and reorganize video clips
- **Audio Integration**: Sync images with voiceover audio
- **Multiple Export Options**: Export as images, clips, or full videos

## Installation

### Prerequisites

1. **Python 3.8+** installed on your system
2. **OpenAI API Key** - Get one from [OpenAI Platform](https://platform.openai.com/api-keys)
3. **FFmpeg** - Required for video processing

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/youtube_automation_app.git
   cd youtube_automation_app
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg:**
   
   **Windows:**
   - Download FFmpeg from [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
   - Extract the archive
   - Copy `ffmpeg.exe` and `ffprobe.exe` to the `ffmpeg/` folder in this project
   
   **Alternative (automatic):**
   - Run the application - it will attempt to download FFmpeg automatically
   - If automatic download fails, follow the manual steps above

4. **Set your OpenAI API key:**
   - Run the application
   - Click "🔑 Set API Key" in the toolbar
   - Enter your OpenAI API key

## Usage

### Running the Application

```bash
python ai_video_tool_openai.py
```

### AI Image Generation

1. **Upload Files:**
   - Click "📄 Choose Script" to select your text script
   - Click "🎙️ Choose Voiceover" to select your audio file

2. **Configure Settings:**
   - Set the number of images to generate
   - Choose an image style (Photorealistic, Cinematic, etc.)
   - Describe your main character(s)

3. **Generate Images:**
   - Click "🚀 Generate Images"
   - The app will create images synchronized with your voiceover

### B-Roll Reorganization

1. **Upload B-Roll:**
   - Click "Choose B-Roll Clips" to select video files
   - Optionally add intro clips and voiceover

2. **Configure Options:**
   - Choose whether to sync with voiceover duration
   - Select overlay options

3. **Reorganize:**
   - Click "🎬 Reorganize B-Roll"
   - The app will shuffle and combine your clips

## File Structure

```
youtube_automation/
├── ai_video_tool_openai.py    # Main application
├── core/                      # Core modules
│   ├── api_manager.py         # API key management
│   ├── openai_generator.py    # DALL-E image generation
│   ├── video_processor.py     # Video processing
│   ├── audio_processor.py     # Audio analysis
│   └── youtube_optimizer.py   # Video optimization
├── ffmpeg/                    # FFmpeg executables (download separately)
├── assets/                    # Application assets
├── output/                    # Generated content
└── requirements.txt           # Python dependencies
```

## Configuration

### API Key Management

The application securely stores your OpenAI API key using the system keyring. You can:
- Set the key through the GUI
- Update it anytime via the "Set API Key" button
- The key is encrypted and stored locally

### FFmpeg Configuration

The application automatically detects FFmpeg in these locations:
1. `ffmpeg/` folder in the project directory
2. System PATH
3. Common installation directories

## Troubleshooting

### Common Issues

1. **"FFmpeg not found"**
   - Download FFmpeg and place executables in the `ffmpeg/` folder
   - Or add FFmpeg to your system PATH

2. **"No module named 'PyQt5'"**
   - Install PyQt5: `pip install PyQt5`

3. **"module 'requests' has no attribute 'get'"**
   - Reinstall requests: `pip install --upgrade --force-reinstall requests`

4. **"API key not found"**
   - Set your OpenAI API key through the GUI
   - Ensure you have a valid API key from OpenAI

### Getting Help

If you encounter issues:
1. Check the console output for error messages
2. Ensure all dependencies are installed
3. Verify your OpenAI API key is valid
4. Check that FFmpeg is properly installed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
