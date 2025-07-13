# File: ai_video_tool_openai.py
# Path: /ai_video_tool_openai.py
# Main application updated to use OpenAI instead of Leonardo AI

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QLineEdit, QTextEdit, QCheckBox, QProgressBar,
    QComboBox, QListWidget, QGroupBox, QScrollArea, QMessageBox, QGridLayout,
    QInputDialog, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QFont
import time
import json
import logging
from pathlib import Path

# Import our custom modules
from core.openai_generator import OpenAIImageGenerator
from core.video_processor import VideoProcessor
from core.audio_processor import AudioProcessor
from core.api_manager import APIKeyManager
from core.youtube_optimizer import YouTubeOptimizer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProcessingThread(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_processing = pyqtSignal()
    error_occurred = pyqtSignal(str)
    image_generated = pyqtSignal(str, str)  # image_path, timestamp

    def __init__(self, task_type, params):
        super().__init__()
        self.task_type = task_type
        self.params = params
        self.is_cancelled = False

    def run(self):
        try:
            if self.task_type == "ai_images":
                self.process_ai_images()
            elif self.task_type == "broll":
                self.process_broll()
        except Exception as e:
            logger.error(f"Processing error: {str(e)}", exc_info=True)
            self.error_occurred.emit(f"Error: {str(e)}")
        finally:
            self.finished_processing.emit()

    def cancel(self):
        self.is_cancelled = True

    def process_ai_images(self):
        self.status_updated.emit("Initializing AI image generation...")
        
        # Extract parameters
        script_path = self.params['script_path']
        voice_path = self.params['voice_path']
        image_count = self.params['image_count']
        style = self.params['style']
        character_desc = self.params['character_desc']
        output_dir = self.params['output_dir']
        
        # Initialize processors with proper instance
        api_manager = APIKeyManager()
        api_key = api_manager.get_api_key()
        if not api_key:
            self.error_occurred.emit("No API key found. Please set your OpenAI API key.")
            return
            
        openai_gen = OpenAIImageGenerator(api_key)
        audio_proc = AudioProcessor()
        video_proc = VideoProcessor()
        
        # Show cost estimate
        cost_estimate = openai_gen.estimate_cost(image_count)
        self.status_updated.emit(f"Estimated cost: ${cost_estimate['total_cost']:.2f} for {image_count} images")
        
        # Read script
        self.status_updated.emit("Reading script file...")
        with open(script_path, 'r', encoding='utf-8') as f:
            script_text = f.read()
        
        # Get audio duration and timestamps
        self.status_updated.emit("Analyzing voiceover duration...")
        duration = audio_proc.get_duration(voice_path)
        timestamps = audio_proc.generate_timestamps(duration, image_count)
        
        # Split script into segments
        script_segments = self._split_script(script_text, image_count)
        
        # Generate images
        generated_images = []
        for i, (segment, timestamp) in enumerate(zip(script_segments, timestamps)):
            if self.is_cancelled:
                self.status_updated.emit("Generation cancelled by user")
                break
                
            self.status_updated.emit(f"Generating image {i+1} of {image_count}...")
            
            # Create prompt
            prompt = openai_gen.create_scene_prompt(
                segment, 
                character_desc, 
                style,
                scene_number=i+1
            )
            
            # Generate image
            try:
                image_path = openai_gen.generate_and_save_image(
                    prompt, 
                    output_dir,
                    f"scene_{i+1:03d}",
                    style
                )
                generated_images.append({
                    'path': image_path,
                    'timestamp': timestamp,
                    'duration': timestamps[i+1] - timestamp if i < len(timestamps)-1 else duration - timestamp
                })
                self.image_generated.emit(image_path, f"{timestamp:.2f}s")
                
            except Exception as e:
                self.status_updated.emit(f"Failed to generate image {i+1}: {str(e)}")
                continue
            
            progress = int((i + 1) / image_count * 100)
            self.progress_updated.emit(progress)
        
        # Save metadata
        metadata_path = os.path.join(output_dir, 'generation_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'images': generated_images,
                'script_path': script_path,
                'voice_path': voice_path,
                'total_duration': duration,
                'character_description': character_desc,
                'style': style,
                'api': 'OpenAI DALL-E 3'
            }, f, indent=2)
        
        # Export based on options
        export_options = self.params['export_options']
        
        if export_options.get('clips', False):
            self.status_updated.emit("Creating video clips from images...")
            video_proc.images_to_clips(generated_images, output_dir)
        
        if export_options.get('full_video', False):
            self.status_updated.emit("Creating full video with voiceover...")
            video_proc.create_full_video(
                generated_images, 
                voice_path, 
                os.path.join(output_dir, 'final_video.mp4')
            )
        
        self.status_updated.emit("AI image generation completed!")

    def process_broll(self):
        self.status_updated.emit("Starting B-roll reorganization...")
        
        # Extract parameters
        broll_paths = self.params['broll_paths']
        intro_paths = self.params.get('intro_paths', [])
        voiceover_path = self.params.get('voiceover_path')
        sync_duration = self.params['sync_duration']
        overlay_audio = self.params['overlay_audio']
        output_dir = self.params['output_dir']
        
        video_proc = VideoProcessor()
        audio_proc = AudioProcessor()
        
        # Get target duration if syncing with voiceover
        target_duration = None
        if sync_duration and voiceover_path:
            self.status_updated.emit("Analyzing voiceover duration...")
            target_duration = audio_proc.get_duration(voiceover_path)
        
        # Process intro clips
        intro_clips = []
        if intro_paths:
            self.status_updated.emit("Processing intro clips...")
            for i, path in enumerate(intro_paths):
                intro_clips.append(path)
                self.progress_updated.emit(int(i / len(intro_paths) * 20))
        
        # Shuffle remaining B-roll
        self.status_updated.emit("Shuffling B-roll clips...")
        import random
        shuffled_broll = broll_paths.copy()
        random.shuffle(shuffled_broll)
        
        # Combine clips
        all_clips = intro_clips + shuffled_broll
        
        # Create reorganized video
        self.status_updated.emit("Creating reorganized video...")
        output_path = os.path.join(output_dir, 'broll_reorganized.mp4')
        
        video_proc.concatenate_clips(
            all_clips, 
            output_path,
            target_duration=target_duration,
            progress_callback=lambda p: self.progress_updated.emit(20 + int(p * 60))
        )
        
        # Overlay audio if requested
        if overlay_audio and voiceover_path:
            self.status_updated.emit("Overlaying voiceover...")
            final_path = os.path.join(output_dir, 'broll_with_voiceover.mp4')
            video_proc.add_audio_to_video(output_path, voiceover_path, final_path)
            self.progress_updated.emit(100)
        else:
            self.progress_updated.emit(100)
        
        self.status_updated.emit("B-roll reorganization completed!")

    def _split_script(self, script, num_segments):
        """Split script into roughly equal segments"""
        words = script.split()
        words_per_segment = len(words) // num_segments
        segments = []
        
        for i in range(num_segments):
            start_idx = i * words_per_segment
            if i == num_segments - 1:
                # Last segment gets remaining words
                segment = ' '.join(words[start_idx:])
            else:
                segment = ' '.join(words[start_idx:start_idx + words_per_segment])
            segments.append(segment)
        
        return segments

class AIVideoTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Visual Builder + B-Roll Reorganizer (OpenAI DALL-E)")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize file paths
        self.script_path = ""
        self.voice_path = ""
        self.broll_paths = []
        self.intro_paths = []
        self.broll_voiceover_path = ""
        
        # Create output directory
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize API key manager as instance
        self.api_manager = APIKeyManager()
        
        # Setup UI
        self._setup_ui()
        
        # Check API key on startup
        self._check_api_key()

    def _setup_ui(self):
        """Setup the main UI"""
        # Create central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add toolbar
        toolbar_layout = QHBoxLayout()
        self.api_status_label = QLabel("API Status: Checking...")
        self.api_key_btn = QPushButton("🔑 Set API Key")
        self.api_key_btn.clicked.connect(self._set_api_key)
        toolbar_layout.addWidget(self.api_status_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.api_key_btn)
        layout.addLayout(toolbar_layout)
        
        # Create tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_ai_image_tab(), "🎨 AI Image Generator")
        self.tabs.addTab(self.create_broll_tab(), "🎞️ B-Roll Reorganizer")
        layout.addWidget(self.tabs)

    def create_ai_image_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create splitter for main content and preview
        splitter = QSplitter(QtCore.Qt.Horizontal)
        
        # Left side - controls
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Script & Voiceover Upload
        upload_box = QGroupBox("🎬 Script & Voiceover Upload")
        upload_layout = QVBoxLayout()
        
        # Script upload
        script_layout = QHBoxLayout()
        self.script_label = QLabel("No script selected")
        self.script_button = QPushButton("📄 Choose Script")
        self.script_button.clicked.connect(self.choose_script_file)
        script_layout.addWidget(self.script_label)
        script_layout.addWidget(self.script_button)
        upload_layout.addLayout(script_layout)
        
        # Voiceover upload
        voice_layout = QHBoxLayout()
        self.voice_label = QLabel("No voiceover selected")
        self.voice_button = QPushButton("🎙️ Choose Voiceover")
        self.voice_button.clicked.connect(self.choose_voiceover_file)
        voice_layout.addWidget(self.voice_label)
        voice_layout.addWidget(self.voice_button)
        upload_layout.addLayout(voice_layout)
        
        upload_box.setLayout(upload_layout)
        left_layout.addWidget(upload_box)
        
        # Image Generation Settings
        settings_box = QGroupBox("🖼️ Image Generation Settings")
        settings_layout = QVBoxLayout()
        
        # Image count
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of Images:"))
        self.image_count = QLineEdit()
        self.image_count.setPlaceholderText("e.g., 5")
        self.image_count.setText("5")
        self.image_count.textChanged.connect(self._update_cost_estimate)
        count_layout.addWidget(self.image_count)
        settings_layout.addLayout(count_layout)
        
        # Cost estimate
        self.cost_label = QLabel("Estimated cost: $0.20 (5 images @ $0.04 each)")
        self.cost_label.setStyleSheet("color: #666; font-style: italic;")
        settings_layout.addWidget(self.cost_label)
        
        # Image style
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Image Style:"))
        self.image_style = QComboBox()
        self.image_style.addItems([
            "Photorealistic",
            "Cinematic",
            "Anime/Manga",
            "3D Render",
            "Oil Painting",
            "Watercolor",
            "Comic Book",
            "Digital Art"
        ])
        style_layout.addWidget(self.image_style)
        settings_layout.addLayout(style_layout)
        
        # Character description
        settings_layout.addWidget(QLabel("Character Description:"))
        self.character_desc = QTextEdit()
        self.character_desc.setPlaceholderText(
            "Describe your main character(s) in detail...\n"
            "e.g., A 30-year-old Black man with short hair, wearing a blue hoodie and jeans"
        )
        self.character_desc.setMaximumHeight(80)
        settings_layout.addWidget(self.character_desc)
        
        settings_box.setLayout(settings_layout)
        left_layout.addWidget(settings_box)
        
        # Export Options
        export_box = QGroupBox("💾 Export Options")
        export_layout = QVBoxLayout()
        self.export_images = QCheckBox("Export Still Images")
        self.export_clips = QCheckBox("Export Timestamped Video Clips")
        self.export_full_video = QCheckBox("Create Full Video with Voiceover")
        self.export_images.setChecked(True)
        self.export_clips.setChecked(True)
        export_layout.addWidget(self.export_images)
        export_layout.addWidget(self.export_clips)
        export_layout.addWidget(self.export_full_video)
        export_box.setLayout(export_layout)
        left_layout.addWidget(export_box)
        
        # Actions
        action_box = QGroupBox("▶️ Actions")
        action_layout = QVBoxLayout()
        
        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("🚀 Generate Images")
        self.generate_btn.clicked.connect(self.generate_images)
        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.cancel_generation)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.generate_btn)
        button_layout.addWidget(self.cancel_btn)
        action_layout.addLayout(button_layout)
        
        self.ai_progress = QProgressBar()
        action_layout.addWidget(self.ai_progress)
        
        self.ai_status = QTextEdit()
        self.ai_status.setReadOnly(True)
        self.ai_status.setMaximumHeight(100)
        action_layout.addWidget(self.ai_status)
        
        self.output_path = QLabel(f"Output: {os.path.abspath(self.output_dir)}")
        self.output_path.setWordWrap(True)
        action_layout.addWidget(self.output_path)
        
        self.open_folder_btn = QPushButton("📂 Open Output Folder")
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        action_layout.addWidget(self.open_folder_btn)
        
        action_box.setLayout(action_layout)
        left_layout.addWidget(action_box)
        
        left_layout.addStretch()
        
        # Right side - preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        preview_box = QGroupBox("🖼️ Generated Images Preview")
        preview_layout = QVBoxLayout()
        
        # Scroll area for images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.preview_widget = QWidget()
        self.preview_grid = QGridLayout(self.preview_widget)
        scroll.setWidget(self.preview_widget)
        preview_layout.addWidget(scroll)
        
        preview_box.setLayout(preview_layout)
        right_layout.addWidget(preview_box)
        
        # Add widgets to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        
        return tab

    def create_broll_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # B-Roll Upload
        broll_box = QGroupBox("🎥 Upload B-Roll")
        broll_layout = QVBoxLayout()
        
        # Main B-roll
        broll_btn_layout = QHBoxLayout()
        self.broll_label = QLabel("No B-roll clips selected")
        self.broll_button = QPushButton("Choose B-Roll Clips")
        self.broll_button.clicked.connect(self.choose_broll_files)
        broll_btn_layout.addWidget(self.broll_label)
        broll_btn_layout.addWidget(self.broll_button)
        broll_layout.addLayout(broll_btn_layout)
        
        # Intro clips
        intro_btn_layout = QHBoxLayout()
        self.intro_label = QLabel("No intro clips selected")
        self.intro_button = QPushButton("Choose Intro Clips (Optional)")
        self.intro_button.clicked.connect(self.choose_intro_files)
        intro_btn_layout.addWidget(self.intro_label)
        intro_btn_layout.addWidget(self.intro_button)
        broll_layout.addLayout(intro_btn_layout)
        
        # Voiceover
        voice_btn_layout = QHBoxLayout()
        self.broll_voice_label = QLabel("No voiceover selected")
        self.broll_voiceover = QPushButton("🎧 Choose Voiceover (Optional)")
        self.broll_voiceover.clicked.connect(self.choose_broll_voiceover)
        voice_btn_layout.addWidget(self.broll_voice_label)
        voice_btn_layout.addWidget(self.broll_voiceover)
        broll_layout.addLayout(voice_btn_layout)
        
        broll_box.setLayout(broll_layout)
        layout.addWidget(broll_box)
        
        # Sync Options
        sync_box = QGroupBox("⚙️ Sync Options")
        sync_layout = QVBoxLayout()
        self.sync_duration = QCheckBox("Sync video to voiceover length")
        self.overlay_audio = QCheckBox("Overlay voiceover on final video")
        self.sync_duration.setChecked(True)
        self.overlay_audio.setChecked(True)
        sync_layout.addWidget(self.sync_duration)
        sync_layout.addWidget(self.overlay_audio)
        sync_box.setLayout(sync_layout)
        layout.addWidget(sync_box)
        
        # Clip List
        clips_box = QGroupBox("📋 Loaded Clips")
        clips_layout = QVBoxLayout()
        self.clips_list = QListWidget()
        clips_layout.addWidget(self.clips_list)
        clips_box.setLayout(clips_layout)
        layout.addWidget(clips_box)
        
        # Actions
        action_box = QGroupBox("▶️ Actions")
        action_layout = QVBoxLayout()
        
        self.broll_btn = QPushButton("🎬 Reorganize B-Roll")
        self.broll_btn.clicked.connect(self.reorganize_broll)
        action_layout.addWidget(self.broll_btn)
        
        self.broll_progress = QProgressBar()
        action_layout.addWidget(self.broll_progress)
        
        self.broll_status = QTextEdit()
        self.broll_status.setReadOnly(True)
        self.broll_status.setMaximumHeight(100)
        action_layout.addWidget(self.broll_status)
        
        self.broll_output_path = QLabel(f"Output: {os.path.abspath(self.output_dir)}")
        self.broll_output_path.setWordWrap(True)
        action_layout.addWidget(self.broll_output_path)
        
        self.broll_open_folder_btn = QPushButton("📂 Open Output Folder")
        self.broll_open_folder_btn.clicked.connect(self.open_output_folder)
        action_layout.addWidget(self.broll_open_folder_btn)
        
        action_box.setLayout(action_layout)
        layout.addWidget(action_box)
        
        return tab

    def _update_cost_estimate(self):
        """Update cost estimate based on number of images"""
        try:
            count = int(self.image_count.text())
            cost = count * 0.04  # $0.04 per image for DALL-E 3
            self.cost_label.setText(f"Estimated cost: ${cost:.2f} ({count} images @ $0.04 each)")
        except:
            self.cost_label.setText("Estimated cost: Enter valid number")

    def _check_api_key(self):
        """Check if API key is set"""
        if self.api_manager.has_api_key():
            self.api_status_label.setText("API Status: ✅ Key Set")
            self.api_status_label.setStyleSheet("color: green")
        else:
            self.api_status_label.setText("API Status: ❌ No Key")
            self.api_status_label.setStyleSheet("color: red")
            QMessageBox.information(
                self, 
                "API Key Required",
                "Please set your OpenAI API key to use the AI image generation feature.\n"
                "Click the 'Set API Key' button in the toolbar.\n\n"
                "Get your API key at: https://platform.openai.com/api-keys"
            )

    def _set_api_key(self):
        """Set API key dialog"""
        current_key = self.api_manager.get_api_key() or ""
        masked_key = f"{current_key[:8]}...{current_key[-4:]}" if len(current_key) > 12 else current_key
        
        key, ok = QInputDialog.getText(
            self,
            "Set OpenAI API Key",
            f"Current key: {masked_key if current_key else 'Not set'}\n\n"
            "Enter your OpenAI API key:\n"
            "(Get it from https://platform.openai.com/api-keys)",
            QLineEdit.Password,
            current_key
        )
        
        if ok and key:
            self.api_manager.set_api_key(key)
            self._check_api_key()
            QMessageBox.information(self, "Success", "API key has been set successfully!")

    def choose_script_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Script File", "", "Text Files (*.txt);;Word Files (*.docx);;All Files (*)"
        )
        if file_path:
            self.script_path = file_path
            self.script_label.setText(f"Script: {os.path.basename(file_path)}")

    def choose_voiceover_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Voiceover File", "", "Audio Files (*.mp3 *.wav *.m4a);;All Files (*)"
        )
        if file_path:
            self.voice_path = file_path
            self.voice_label.setText(f"Voice: {os.path.basename(file_path)}")

    def choose_broll_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose B-Roll Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        if file_paths:
            self.broll_paths = file_paths
            self.broll_label.setText(f"{len(file_paths)} clips selected")
            self._update_clips_list()

    def choose_intro_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose Intro Files", "", "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        if file_paths:
            self.intro_paths = file_paths
            self.intro_label.setText(f"{len(file_paths)} intro clips selected")
            self._update_clips_list()

    def choose_broll_voiceover(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Choose B-Roll Voiceover", "", "Audio Files (*.mp3 *.wav *.m4a);;All Files (*)"
        )
        if file_path:
            self.broll_voiceover_path = file_path
            self.broll_voice_label.setText(f"Voice: {os.path.basename(file_path)}")

    def _update_clips_list(self):
        """Update the clips list widget"""
        self.clips_list.clear()
        
        if self.intro_paths:
            self.clips_list.addItem("=== INTRO CLIPS ===")
            for path in self.intro_paths:
                self.clips_list.addItem(f"  📹 {os.path.basename(path)}")
        
        if self.broll_paths:
            self.clips_list.addItem("=== B-ROLL CLIPS ===")
            for path in self.broll_paths:
                self.clips_list.addItem(f"  🎬 {os.path.basename(path)}")

    def generate_images(self):
        if not self.script_path or not self.voice_path:
            QMessageBox.warning(self, "Missing Files", "Please select both script and voiceover files first.")
            return
        
        if not self.api_manager.has_api_key():
            QMessageBox.warning(self, "No API Key", "Please set your OpenAI API key first.")
            return
        
        try:
            image_count = int(self.image_count.text())
            if image_count <= 0:
                raise ValueError("Image count must be positive")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number for image count.")
            return
        
        character_desc = self.character_desc.toPlainText().strip()
        if not character_desc:
            QMessageBox.warning(self, "Missing Description", "Please provide a character description.")
            return
        
        # Show cost confirmation
        cost = image_count * 0.04
        reply = QMessageBox.question(
            self,
            "Confirm Generation",
            f"This will generate {image_count} images at an estimated cost of ${cost:.2f}.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Create timestamped output directory
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        session_output_dir = os.path.join(self.output_dir, f"ai_images_{timestamp}")
        os.makedirs(session_output_dir, exist_ok=True)
        
        # Update UI
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.ai_progress.setValue(0)
        self.ai_status.clear()
        self.preview_grid.setParent(None)
        self.preview_grid = QGridLayout(self.preview_widget)
        
        params = {
            'script_path': self.script_path,
            'voice_path': self.voice_path,
            'image_count': image_count,
            'style': self.image_style.currentText(),
            'character_desc': character_desc,
            'export_options': {
                'images': self.export_images.isChecked(),
                'clips': self.export_clips.isChecked(),
                'full_video': self.export_full_video.isChecked()
            },
            'output_dir': session_output_dir
        }
        
        self.ai_thread = ProcessingThread("ai_images", params)
        self.ai_thread.progress_updated.connect(self.ai_progress.setValue)
        self.ai_thread.status_updated.connect(self.ai_status.append)
        self.ai_thread.error_occurred.connect(self._handle_error)
        self.ai_thread.image_generated.connect(self._add_image_preview)
        self.ai_thread.finished_processing.connect(self._ai_generation_finished)
        self.ai_thread.start()

    def cancel_generation(self):
        if hasattr(self, 'ai_thread') and self.ai_thread.isRunning():
            self.ai_thread.cancel()
            self.ai_status.append("Cancelling generation...")

    def _ai_generation_finished(self):
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _add_image_preview(self, image_path, timestamp):
        """Add image to preview grid"""
        row = self.preview_grid.rowCount()
        
        # Create image widget
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        
        # Load and scale image
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        
        # Image label
        image_label = QLabel()
        image_label.setPixmap(scaled_pixmap)
        image_label.setAlignment(QtCore.Qt.AlignCenter)
        
        # Timestamp label
        time_label = QLabel(f"@ {timestamp}")
        time_label.setAlignment(QtCore.Qt.AlignCenter)
        
        image_layout.addWidget(image_label)
        image_layout.addWidget(time_label)
        
        # Add to grid (3 columns)
        col = (row - 1) % 3
        row = (row - 1) // 3
        self.preview_grid.addWidget(image_widget, row, col)

    def reorganize_broll(self):
        if not self.broll_paths:
            QMessageBox.warning(self, "Missing Files", "Please select B-roll files first.")
            return
        
        # Check FFmpeg availability for B-roll processing
        video_proc = VideoProcessor()
        if not video_proc.check_ffmpeg():
            QMessageBox.critical(
                self,
                "FFmpeg Required",
                "The B-Roll reorganization feature requires FFmpeg to be installed.\n\n"
                "Please install FFmpeg first:\n"
                "1. Download from: https://www.gyan.dev/ffmpeg/builds/\n"
                "2. Extract and place ffmpeg.exe in the 'ffmpeg' folder\n"
                "3. Restart the application"
            )
            return
        
        # Create timestamped output directory
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        session_output_dir = os.path.join(self.output_dir, f"broll_{timestamp}")
        os.makedirs(session_output_dir, exist_ok=True)
        
        self.broll_btn.setEnabled(False)
        self.broll_progress.setValue(0)
        self.broll_status.clear()
        
        params = {
            'broll_paths': self.broll_paths,
            'intro_paths': self.intro_paths,
            'voiceover_path': self.broll_voiceover_path,
            'sync_duration': self.sync_duration.isChecked(),
            'overlay_audio': self.overlay_audio.isChecked(),
            'output_dir': session_output_dir
        }
        
        self.broll_thread = ProcessingThread("broll", params)
        self.broll_thread.progress_updated.connect(self.broll_progress.setValue)
        self.broll_thread.status_updated.connect(self.broll_status.append)
        self.broll_thread.error_occurred.connect(self._handle_error)
        self.broll_thread.finished_processing.connect(lambda: self.broll_btn.setEnabled(True))
        self.broll_thread.start()

    def _handle_error(self, error_msg):
        QMessageBox.critical(self, "Error", error_msg)

    def open_output_folder(self):
        try:
            if sys.platform == 'win32':
                os.startfile(self.output_dir)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{self.output_dir}"')
            else:  # Linux
                os.system(f'xdg-open "{self.output_dir}"')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    # Set application icon and metadata
    app.setApplicationName("AI Video Tool")
    app.setOrganizationName("YourCompany")
    
    window = AIVideoTool()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()