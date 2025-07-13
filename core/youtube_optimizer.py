# File: youtube_optimizer.py
# Path: /core/youtube_optimizer.py

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class YouTubeOptimizer:
    """Optimize content for YouTube upload and compliance"""
    
    # YouTube recommended specifications
    YOUTUBE_SPECS = {
        'video': {
            'codec': 'h264',
            'profile': 'high',
            'level': '4.0',
            'pixel_format': 'yuv420p',
            'bitrate': {
                '1080p': '8000k',
                '720p': '5000k',
                '480p': '2500k'
            }
        },
        'audio': {
            'codec': 'aac',
            'bitrate': '192k',
            'sample_rate': '48000',
            'channels': 2
        },
        'container': 'mp4',
        'max_file_size': 128 * 1024 * 1024 * 1024,  # 128GB
        'max_duration': 12 * 60 * 60  # 12 hours
    }
    
    def __init__(self):
        self.metadata_template = self._get_metadata_template()
    
    def _get_metadata_template(self) -> Dict:
        """Get template for video metadata"""
        return {
            'title': '',
            'description': '',
            'tags': [],
            'category': '',
            'thumbnail': '',
            'ai_disclosure': True,  # Required for AI-generated content
            'creation_date': datetime.now().isoformat(),
            'tool_version': '1.0.0'
        }
    
    def generate_ffmpeg_params(self, resolution: str = '1080p') -> List[str]:
        """Generate FFmpeg parameters for YouTube optimization"""
        
        video_bitrate = self.YOUTUBE_SPECS['video']['bitrate'].get(resolution, '8000k')
        
        params = [
            # Video encoding
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-profile:v', 'high',
            '-level', '4.0',
            '-pix_fmt', 'yuv420p',
            '-b:v', video_bitrate,
            '-maxrate', video_bitrate,
            '-bufsize', f"{int(video_bitrate[:-1]) * 2}k",
            
            # Audio encoding
            '-c:a', 'aac',
            '-b:a', self.YOUTUBE_SPECS['audio']['bitrate'],
            '-ar', str(self.YOUTUBE_SPECS['audio']['sample_rate']),
            '-ac', str(self.YOUTUBE_SPECS['audio']['channels']),
            
            # Container settings
            '-movflags', '+faststart',  # Move moov atom to beginning
            '-f', 'mp4'
        ]
        
        return params
    
    def create_metadata_file(self, video_path: str, metadata: Dict) -> str:
        """Create metadata file for video"""
        
        metadata_path = video_path.replace('.mp4', '_metadata.json')
        
        # Ensure AI disclosure is set
        metadata['ai_disclosure'] = True
        metadata['ai_disclosure_notice'] = (
            "This video contains AI-generated content. "
            "Images were created using Leonardo AI based on the provided script."
        )
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Created metadata file: {metadata_path}")
        return metadata_path
    
    def generate_seo_suggestions(self, script_text: str, character_desc: str) -> Dict:
        """Generate SEO suggestions based on content"""
        
        suggestions = {
            'title_tips': [
                "Keep title under 70 characters",
                "Include main keyword at the beginning",
                "Use numbers or 'How to' for better CTR",
                "Add emotional triggers (Amazing, Incredible, etc.)"
            ],
            'description_template': f"""
[Brief compelling hook - 1-2 sentences]

In this video, you'll discover:
• [Key point 1]
• [Key point 2]
• [Key point 3]

🤖 AI Disclosure: This video uses AI-generated visuals created with Leonardo AI.

⏱️ Timestamps:
00:00 - Introduction
[Add more timestamps based on your scenes]

📝 Character: {character_desc}

🔗 Links:
[Add any relevant links]

#AIGenerated #DALLE3 #[YourNiche] #[MoreRelevantHashtags]
            """.strip(),
            'recommended_tags': [
                "AI generated",
                "Leonardo AI",
                "AI video",
                "automated content",
                # Add niche-specific tags based on content
            ],
            'thumbnail_tips': [
                "Use high contrast colors",
                "Include text overlay (max 3-4 words)",
                "Show emotional face or key scene",
                "Resolution: 1280x720 minimum",
                "File size: Under 2MB"
            ]
        }
        
        return suggestions
    
    def validate_video_file(self, video_path: str) -> Dict:
        """Validate video file meets YouTube requirements"""
        
        import subprocess
        
        # Get video information using ffprobe
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(result.stdout)
            
            validation = {
                'valid': True,
                'issues': [],
                'warnings': []
            }
            
            # Check file size
            file_size = os.path.getsize(video_path)
            if file_size > self.YOUTUBE_SPECS['max_file_size']:
                validation['valid'] = False
                validation['issues'].append(f"File size exceeds YouTube limit: {file_size / (1024**3):.2f}GB")
            
            # Check duration
            duration = float(info['format'].get('duration', 0))
            if duration > self.YOUTUBE_SPECS['max_duration']:
                validation['valid'] = False
                validation['issues'].append(f"Duration exceeds YouTube limit: {duration/3600:.2f} hours")
            
            # Check video codec
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            if video_stream:
                if video_stream['codec_name'] != 'h264':
                    validation['warnings'].append(f"Video codec {video_stream['codec_name']} may need re-encoding")
            
            # Check audio codec
            audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
            if audio_stream:
                if audio_stream['codec_name'] not in ['aac', 'mp3']:
                    validation['warnings'].append(f"Audio codec {audio_stream['codec_name']} may need re-encoding")
            
            validation['file_info'] = {
                'size_gb': file_size / (1024**3),
                'duration_minutes': duration / 60,
                'video_codec': video_stream['codec_name'] if video_stream else None,
                'audio_codec': audio_stream['codec_name'] if audio_stream else None,
                'resolution': f"{video_stream.get('width')}x{video_stream.get('height')}" if video_stream else None
            }
            
            return validation
            
        except Exception as e:
            logger.error(f"Failed to validate video: {str(e)}")
            return {
                'valid': False,
                'issues': [f"Validation failed: {str(e)}"],
                'warnings': []
            }
    
    def create_upload_checklist(self) -> List[str]:
        """Create a checklist for YouTube upload"""
        
        return [
            "✅ Video file is under 128GB",
            "✅ Video duration is under 12 hours",
            "✅ Video format is MP4 with H.264 codec",
            "✅ Audio is AAC at 48kHz",
            "✅ Title is under 100 characters",
            "✅ Description includes AI disclosure",
            "✅ AI content disclosure is enabled in YouTube Studio",
            "✅ Thumbnail is created (1280x720 minimum)",
            "✅ Tags include 'AI generated' and relevant keywords",
            "✅ Category is selected appropriately",
            "✅ Captions/subtitles are added if available",
            "✅ End screen and cards are configured",
            "✅ Monetization settings are configured (if eligible)"
        ]