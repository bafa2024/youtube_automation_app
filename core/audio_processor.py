# File: audio_processor.py
# Path: /core/audio_processor.py

import os
import logging
import wave
import contextlib
from typing import List, Tuple

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing operations"""
    
    def __init__(self):
        # Check if FFmpeg is available by testing pydub
        self.ffmpeg_available = self._check_ffmpeg_availability()
        
        if self.ffmpeg_available:
            try:
                from pydub import AudioSegment
                from pydub.utils import mediainfo
                self.AudioSegment = AudioSegment
                self.mediainfo = mediainfo
                logger.info("FFmpeg available - full audio processing enabled")
            except Exception as e:
                logger.warning(f"Failed to import pydub: {e}")
                self.ffmpeg_available = False
        else:
            logger.warning("FFmpeg not available - limited audio processing only")
    
    def _check_ffmpeg_availability(self) -> bool:
        """Check if FFmpeg is available on the system"""
        import subprocess
        
        # Common FFmpeg paths
        possible_paths = [
            "ffmpeg",
            "ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, "-version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logger.info(f"Found FFmpeg at: {path}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
        
        logger.warning("FFmpeg not found in system PATH")
        return False
    
    def get_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds"""
        
        logger.info(f"Getting duration of {audio_path}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Try WAV files first (no FFmpeg needed)
        if audio_path.lower().endswith('.wav'):
            try:
                with wave.open(audio_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / float(rate)
                    logger.info(f"WAV duration: {duration:.2f} seconds")
                    return duration
            except Exception as e:
                logger.warning(f"WAV parsing failed: {str(e)}")
        
        # If FFmpeg is available, try pydub
        if self.ffmpeg_available:
            try:
                audio = self.AudioSegment.from_file(audio_path)
                duration = len(audio) / 1000.0  # Convert milliseconds to seconds
                logger.info(f"Pydub duration: {duration:.2f} seconds")
                return duration
            except Exception as e:
                logger.warning(f"Pydub failed: {str(e)}")
        
        # Fallback to file size estimation
        try:
            file_size = os.path.getsize(audio_path)
            # Rough estimation based on common bitrates
            if audio_path.lower().endswith('.mp3'):
                # Assume 128kbps for MP3
                estimated_duration = (file_size * 8) / (128 * 1000)
            elif audio_path.lower().endswith('.m4a'):
                # Assume 256kbps for M4A
                estimated_duration = (file_size * 8) / (256 * 1000)
            else:
                # Default to 128kbps
                estimated_duration = (file_size * 8) / (128 * 1000)
            
            logger.warning(f"Using estimated duration: {estimated_duration:.2f} seconds (based on file size)")
            return estimated_duration
            
        except Exception as e:
            logger.error(f"All duration methods failed: {str(e)}")
            raise RuntimeError("Cannot determine audio duration - FFmpeg is required for accurate audio processing")
    
    def get_duration_fallback(self, audio_path: str) -> float:
        """Get audio duration using alternative methods that don't require FFmpeg"""
        
        logger.info(f"Getting duration using fallback method for {audio_path}")
        
        # Try using wave module for WAV files
        if audio_path.lower().endswith('.wav'):
            try:
                with wave.open(audio_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / float(rate)
                    logger.info(f"WAV duration: {duration:.2f} seconds")
                    return duration
            except Exception as e:
                logger.warning(f"WAV fallback failed: {str(e)}")
        
        # Try using basic file size estimation (very rough)
        try:
            file_size = os.path.getsize(audio_path)
            # Rough estimation: assume 128kbps bitrate
            # This is very approximate and should only be used as last resort
            estimated_duration = (file_size * 8) / (128 * 1000)  # seconds
            logger.warning(f"Using estimated duration: {estimated_duration:.2f} seconds (based on file size)")
            return estimated_duration
        except Exception as e:
            logger.error(f"All duration methods failed: {str(e)}")
            raise RuntimeError("Cannot determine audio duration - FFmpeg is required for accurate audio processing")
    
    def generate_timestamps(self, total_duration: float, num_segments: int) -> List[float]:
        """Generate evenly spaced timestamps"""
        
        if num_segments <= 0:
            raise ValueError("Number of segments must be positive")
        
        segment_duration = total_duration / num_segments
        timestamps = []
        
        for i in range(num_segments):
            timestamp = i * segment_duration
            timestamps.append(timestamp)
        
        logger.info(f"Generated {num_segments} timestamps for {total_duration:.2f}s audio")
        return timestamps
    
    def split_audio(self, audio_path: str, timestamps: List[float], 
                   output_dir: str) -> List[str]:
        """Split audio file at given timestamps"""
        
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available - cannot split audio")
            raise RuntimeError("Audio processing not available - FFmpeg may not be installed")
        
        logger.info(f"Splitting audio into {len(timestamps)} segments")
        
        audio = self.AudioSegment.from_file(audio_path)
        output_paths = []
        
        for i in range(len(timestamps)):
            start_time = int(timestamps[i] * 1000)  # Convert to milliseconds
            
            if i < len(timestamps) - 1:
                end_time = int(timestamps[i + 1] * 1000)
            else:
                end_time = len(audio)
            
            # Extract segment
            segment = audio[start_time:end_time]
            
            # Save segment
            output_path = os.path.join(output_dir, f"segment_{i+1:03d}.mp3")
            segment.export(output_path, format="mp3", bitrate="192k")
            output_paths.append(output_path)
            
            logger.info(f"Created segment {i+1}: {start_time/1000:.2f}s - {end_time/1000:.2f}s")
        
        return output_paths
    
    def normalize_audio(self, audio_path: str, target_dBFS: float = -20.0) -> str:
        """Normalize audio volume"""
        
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available - cannot normalize audio")
            raise RuntimeError("Audio processing not available - FFmpeg may not be installed")
        
        logger.info(f"Normalizing audio to {target_dBFS} dBFS")
        
        audio = self.AudioSegment.from_file(audio_path)
        
        # Calculate normalization needed
        change_in_dBFS = target_dBFS - audio.dBFS
        
        # Apply normalization
        normalized = audio.apply_gain(change_in_dBFS)
        
        # Save normalized audio
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_normalized{ext}"
        
        normalized.export(output_path, format=ext[1:], bitrate="192k")
        logger.info(f"Normalized audio saved to: {output_path}")
        
        return output_path
    
    def combine_audio_files(self, audio_paths: List[str], output_path: str):
        """Combine multiple audio files into one"""
        
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available - cannot combine audio files")
            raise RuntimeError("Audio processing not available - FFmpeg may not be installed")
        
        logger.info(f"Combining {len(audio_paths)} audio files")
        
        combined = self.AudioSegment.empty()
        
        for path in audio_paths:
            audio = self.AudioSegment.from_file(path)
            combined += audio
        
        # Export combined audio
        combined.export(output_path, format="mp3", bitrate="192k")
        logger.info(f"Combined audio saved to: {output_path}")
    
    def add_fade_effects(self, audio_path: str, fade_in_ms: int = 1000, 
                        fade_out_ms: int = 1000) -> str:
        """Add fade in/out effects to audio"""
        
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available - cannot add fade effects")
            raise RuntimeError("Audio processing not available - FFmpeg may not be installed")
        
        logger.info(f"Adding fade effects: in={fade_in_ms}ms, out={fade_out_ms}ms")
        
        audio = self.AudioSegment.from_file(audio_path)
        
        # Apply fades
        audio = audio.fade_in(fade_in_ms).fade_out(fade_out_ms)
        
        # Save
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_faded{ext}"
        
        audio.export(output_path, format=ext[1:], bitrate="192k")
        logger.info(f"Audio with fades saved to: {output_path}")
        
        return output_path
    
    def extract_audio_segment(self, audio_path: str, start_time: float, 
                            end_time: float, output_path: str):
        """Extract a segment from audio file"""
        
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available - cannot extract audio segment")
            raise RuntimeError("Audio processing not available - FFmpeg may not be installed")
        
        logger.info(f"Extracting segment: {start_time:.2f}s - {end_time:.2f}s")
        
        audio = self.AudioSegment.from_file(audio_path)
        
        start_ms = int(start_time * 1000)
        end_ms = int(end_time * 1000)
        
        segment = audio[start_ms:end_ms]
        segment.export(output_path, format="mp3", bitrate="192k")
        
        logger.info(f"Segment saved to: {output_path}")
    
    def analyze_audio_levels(self, audio_path: str) -> dict:
        """Analyze audio levels and properties"""
        
        if not self.ffmpeg_available:
            logger.error("FFmpeg not available - cannot analyze audio")
            raise RuntimeError("Audio processing not available - FFmpeg may not be installed")
        
        audio = self.AudioSegment.from_file(audio_path)
        
        analysis = {
            'duration_seconds': len(audio) / 1000.0,
            'channels': audio.channels,
            'sample_rate': audio.frame_rate,
            'dBFS': audio.dBFS,
            'max_dBFS': audio.max_dBFS,
            'rms': audio.rms,
            'max_possible_amplitude': audio.max_possible_amplitude
        }
        
        logger.info(f"Audio analysis: {analysis}")
        return analysis