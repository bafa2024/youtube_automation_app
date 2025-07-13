# File: video_processor.py
# Path: /core/video_processor.py

import os
import sys
import subprocess
import logging
from typing import List, Dict, Optional, Callable
# Import from moviepy.editor (the high-level API) instead of the base package
from moviepy.editor import (
    VideoFileClip, ImageClip, CompositeVideoClip,
    concatenate_videoclips, AudioFileClip,
)
import tempfile
import shutil
import traceback

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Handles video processing operations"""
    
    def _ensure_writable_path(self, path: str) -> str:
        """Ensure the path is writable, create temp path if needed"""
        try:
            # Try to create parent directory
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Test write permission
            test_file = os.path.join(os.path.dirname(path), '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                return path
            except:
                # Fall back to temp directory
                temp_dir = tempfile.mkdtemp(prefix='aivideo_')
                new_path = os.path.join(temp_dir, os.path.basename(path))
                logger.warning(f"No write permission for {path}, using {new_path}")
                return new_path
        except Exception as e:
            # Ultimate fallback
            temp_dir = tempfile.mkdtemp(prefix='aivideo_')
            new_path = os.path.join(temp_dir, os.path.basename(path))
            logger.warning(f"Path error for {path}: {e}, using {new_path}")
            return new_path

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temp directory: {self.temp_dir}")
        
        # Find and set FFmpeg path
        self.ffmpeg_path = self._find_ffmpeg()
        if self.ffmpeg_path:
            # Set environment variables for MoviePy
            os.environ['IMAGEIO_FFMPEG_EXE'] = self.ffmpeg_path
            os.environ['FFMPEG_BINARY'] = self.ffmpeg_path
            
            # Configure MoviePy to use our FFmpeg
            try:
                from moviepy.config import change_settings
                change_settings({"FFMPEG_BINARY": self.ffmpeg_path})
            except:
                pass
    
    def __del__(self):
        """Cleanup temp directory"""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info("Cleaned up temp directory")
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable"""
        # Check common locations
        ffmpeg_paths = [
            "ffmpeg.exe",
            "ffmpeg/ffmpeg.exe",
            "bin/ffmpeg.exe",
            os.path.join(os.path.dirname(__file__), "..", "ffmpeg", "ffmpeg.exe"),
            os.path.join(os.path.dirname(__file__), "..", "ffmpeg.exe"),
            os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe"),
            os.path.join(os.getcwd(), "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
        ]
        
        # Check environment variable
        if os.environ.get('FFMPEG_BINARY'):
            ffmpeg_paths.insert(0, os.environ['FFMPEG_BINARY'])
        
        # Check if running from PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # Running in a bundle
            bundle_dir = os.path.dirname(sys.executable)
            bundle_ffmpeg_paths = [
                os.path.join(bundle_dir, "ffmpeg.exe"),
                os.path.join(bundle_dir, "ffmpeg", "ffmpeg.exe"),
            ]
            ffmpeg_paths = bundle_ffmpeg_paths + ffmpeg_paths
        
        for path in ffmpeg_paths:
            if os.path.exists(path):
                abs_path = os.path.abspath(path)
                logger.info(f"Found FFmpeg at: {abs_path}")
                return abs_path
        
        # Try system path
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
            if result.returncode == 0:
                logger.info("Found FFmpeg in system PATH")
                return "ffmpeg"
        except:
            pass
        
        logger.warning("FFmpeg not found! Video processing may fail.")
        return None
    
    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available"""
        if not self.ffmpeg_path:
            self.ffmpeg_path = self._find_ffmpeg()
        
        if self.ffmpeg_path and self.ffmpeg_path != "ffmpeg":
            # Test specific path
            try:
                result = subprocess.run([self.ffmpeg_path, '-version'], capture_output=True)
                return result.returncode == 0
            except:
                return False
        elif self.ffmpeg_path == "ffmpeg":
            # Test system command
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
                return result.returncode == 0
            except:
                return False
        
        return False
    
    def images_to_clips(self, image_data: List[Dict], output_dir: str):
        """Convert images to video clips based on timestamps"""
        
        for i, data in enumerate(image_data):
            image_path = data['path']
            duration = data['duration']
            
            logger.info(f"Creating video clip from {image_path} (duration: {duration}s)")
            
            # Create video clip from image
            clip = ImageClip(image_path, duration=duration)
            
            # Note: fadein/fadeout methods removed in newer MoviePy versions
            # clip = clip.fadein(0.5).fadeout(0.5)  # type: ignore
            
            # Export clip
            output_path = os.path.join(output_dir, f"scene_{i+1:03d}.mp4")
            clip.write_videofile(
                output_path,
                fps=30,
                codec='libx264',
                audio=False,
                preset='medium',
                threads=4
            )
            clip.close()
    
    def create_full_video(self, image_data: List[Dict], audio_path: str, 
                         output_path: str):
        """Create full video from images with voiceover"""
        
        logger.info("Creating full video with voiceover...")
        
        # Load audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        
        # Create clips from images
        clips = []
        for i, data in enumerate(image_data):
            image_path = data['path']
            duration = data['duration']
            
            # Create image clip
            clip = ImageClip(image_path, duration=duration)
            
            # Note: fadein/fadeout methods removed in newer MoviePy versions
            # Add transitions
            # if i > 0:
            #     clip = clip.fadein(0.5)  # type: ignore
            # if i < len(image_data) - 1:
            #     clip = clip.fadeout(0.5)  # type: ignore
            
            clips.append(clip)
        
        # Concatenate all clips
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Set audio
        final_video = final_video.set_audio(audio)
        
        # Ensure video matches audio duration
        if final_video.duration > total_duration:
            final_video = final_video.subclip(0, total_duration)
        elif final_video.duration < total_duration:
            # Extend last frame
            last_frame = final_video.to_ImageClip(t=final_video.duration-0.1)
            extension = last_frame.set_duration(total_duration - final_video.duration)
            final_video = concatenate_videoclips([final_video, extension])
        
        # Export with YouTube-optimized settings
        self._export_for_youtube(final_video, self._ensure_writable_path(output_path))
        
        # Cleanup
        final_video.close()
        audio.close()
    
    def concatenate_clips(self, video_paths: List[str], output_path: str,
                         target_duration: Optional[float] = None,
                         progress_callback: Optional[Callable] = None):
        """Concatenate multiple video clips"""
        
        logger.info(f"Concatenating {len(video_paths)} video clips...")
        
        # Use FFmpeg for better performance with many clips
        if len(video_paths) > 10:
            self._concatenate_with_ffmpeg(video_paths, output_path, target_duration)
        else:
            self._concatenate_with_moviepy(video_paths, output_path, 
                                          target_duration, progress_callback)
    
    def _concatenate_with_moviepy(self, video_paths: List[str], output_path: str,
                                  target_duration: Optional[float] = None,
                                  progress_callback: Optional[Callable] = None):
        """Concatenate using MoviePy (better for small number of clips)"""
        
        clips = []
        total_duration = 0
        
        # Load clips
        for i, path in enumerate(video_paths):
            try:
                clip = VideoFileClip(path)
                clips.append(clip)
                total_duration += clip.duration
                
                if progress_callback:
                    progress = (i / len(video_paths)) * 0.5  # First 50% for loading
                    progress_callback(progress)
                    
            except Exception as e:
                logger.error(f"Error loading clip {path}: {str(e)}")
                continue
        
        if not clips:
            raise ValueError("No valid video clips to concatenate")
        
        # Concatenate
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Trim to target duration if specified
        if target_duration and final_video.duration > target_duration:
            final_video = final_video.subclip(0, target_duration)
        
        # Export
        self._export_for_youtube(final_video, self._ensure_writable_path(output_path))
        
        # Update progress to 100% after export
        if progress_callback:
            progress_callback(1.0)
        
        # Cleanup
        for clip in clips:
            clip.close()
        final_video.close()
    
    def _concatenate_with_ffmpeg(self, video_paths: List[str], output_path: str,
                                target_duration: Optional[float] = None):
        """Concatenate using FFmpeg (better performance for many clips)"""
        
        # Ensure temp_dir exists
        if not hasattr(self, 'temp_dir') or not self.temp_dir or not os.path.exists(self.temp_dir):
            self.temp_dir = tempfile.mkdtemp()
            logger.warning(f"temp_dir was missing, recreated: {self.temp_dir}")
        
        # Create file list for FFmpeg
        list_file = os.path.join(self.temp_dir, 'concat_list.txt')
        logger.info(f"Creating concat list file: {list_file}")
        
        # Ensure the temp directory exists and is writable
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            logger.info(f"Ensured temp directory exists: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Failed to create temp directory: {e}")
            raise RuntimeError(f"Failed to create temp directory: {e}")
        
        # Write the concat list file with robust error handling
        try:
            logger.info(f"Opening file for writing: {list_file}")
            with open(list_file, 'w', encoding='utf-8') as f:
                logger.info(f"Successfully opened {list_file} for writing")
                
                for i, path in enumerate(video_paths):
                    if not os.path.exists(path):
                        logger.warning(f"Video file not found: {path}")
                        continue
                    
                    abs_path = os.path.abspath(path)
                    logger.info(f"Writing video {i+1}/{len(video_paths)}: {abs_path}")
                    f.write(f"file '{abs_path}'\n")
                
                logger.info(f"Successfully wrote {len(video_paths)} video paths to concat list")
                
        except Exception as e:
            logger.error(f"Failed to write concat list file: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Failed to write concat list file: {e}")
        
        # Verify the file was written
        if not os.path.exists(list_file):
            logger.error(f"Concat list file was not created: {list_file}")
            raise RuntimeError(f"Concat list file was not created: {list_file}")
        
        # Check file size
        try:
            file_size = os.path.getsize(list_file)
            logger.info(f"Concat list file size: {file_size} bytes")
            if file_size == 0:
                logger.error("Concat list file is empty")
                raise RuntimeError("Concat list file is empty")
        except Exception as e:
            logger.error(f"Failed to check concat list file: {e}")
            raise RuntimeError(f"Failed to check concat list file: {e}")
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',  # Copy codecs for speed
        ]
        
        # Add duration limit if specified
        if target_duration:
            cmd.extend(['-t', str(target_duration)])
        
        cmd.extend([
            '-y',  # Overwrite output
            output_path
        ])
        
        # Execute FFmpeg
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("FFmpeg completed successfully")
            logger.debug(f"FFmpeg stdout: {result.stdout}")
            logger.debug(f"FFmpeg stderr: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed with return code {e.returncode}")
            logger.error(f"FFmpeg stdout: {e.stdout}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            raise RuntimeError(f"FFmpeg failed: {e.stderr}")
        except Exception as e:
            logger.error(f"FFmpeg execution error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise RuntimeError(f"FFmpeg execution error: {e}")
        
        # Verify output file was created
        if not os.path.exists(output_path):
            logger.error(f"Output file was not created: {output_path}")
            raise RuntimeError(f"Output file was not created: {output_path}")
        
        logger.info(f"Successfully created concatenated video: {output_path}")
    
    def add_audio_to_video(self, video_path: str, audio_path: str, 
                          output_path: str):
        """Add audio track to video"""
        
        logger.info("Adding audio to video...")
        
        # Use FFmpeg for better performance
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',  # Copy video codec
            '-c:a', 'aac',   # Encode audio as AAC
            '-b:a', '192k',  # Audio bitrate
            '-map', '0:v:0',  # Use video from first input
            '-map', '1:a:0',  # Use audio from second input
            '-shortest',  # Match shortest stream
            '-y',
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Created video with audio: {output_path}")
    
    def _export_for_youtube(self, video_clip, output_path: str,
                           progress_callback: Optional[Callable] = None):
        """Export video with YouTube-optimized settings"""
        
        logger.info("Exporting with YouTube-optimized settings...")
        
        # YouTube recommended settings
        export_params = {
            'codec': 'libx264',
            'audio_codec': 'aac',
            'audio_bitrate': '192k',
            'preset': 'medium',  # Balance between speed and compression
            'threads': 4,
            'fps': 30,
        }
        
        # Calculate bitrate based on resolution
        if hasattr(video_clip, 'h'):
            height = video_clip.h
            if height >= 1080:
                export_params['bitrate'] = '8000k'
            elif height >= 720:
                export_params['bitrate'] = '5000k'
            else:
                export_params['bitrate'] = '2500k'
        
        video_clip.write_videofile(output_path, **export_params)
    
    def extract_audio(self, video_path: str, output_path: str):
        """Extract audio from video file"""
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # No video
            '-acodec', 'copy',
            '-y',
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Extracted audio to: {output_path}")