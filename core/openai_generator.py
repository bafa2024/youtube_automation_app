# File: openai_generator.py
# Path: /core/openai_generator.py

import os
import time
import requests
import logging
from typing import List, Dict, Optional, Tuple
import json
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAIImageGenerator:
    """Handles AI image generation using OpenAI's DALL-E API"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.generation_history = []
        
    def create_scene_prompt(self, script_segment: str, character_desc: str, 
                          style: str, scene_number: int) -> str:
        """Create a detailed prompt for DALL-E based on script segment"""
        
        # Base prompt structure for consistency
        base_prompt = f"""Create a {style.lower()} style image. 

Main character: {character_desc}

Scene {scene_number} context: {script_segment}

Important guidelines:
- Maintain exact same character appearance as described
- {self._get_style_guidelines(style)}
- Professional quality suitable for video content
- Clear focal point on the main character
- Appropriate lighting and composition"""

        # Add style-specific enhancements
        if style == "Cinematic":
            base_prompt += "\n- Wide aspect ratio feeling, dramatic lighting"
            base_prompt += "\n- Film grain texture, color grading like a movie"
        elif style == "Photorealistic":
            base_prompt += "\n- Ultra realistic details, natural lighting"
            base_prompt += "\n- Shot with professional camera, shallow depth of field"
            
        return base_prompt
    
    def _get_style_guidelines(self, style: str) -> str:
        """Get style-specific guidelines"""
        style_guides = {
            "Photorealistic": "Realistic proportions, natural textures, authentic environments",
            "Cinematic": "Movie-like composition, dramatic angles, film color grading",
            "Anime/Manga": "Japanese animation style, expressive features, vibrant colors",
            "3D Render": "Pixar-like quality, smooth surfaces, ambient occlusion",
            "Oil Painting": "Visible brush strokes, rich textures, classical composition",
            "Watercolor": "Soft edges, flowing colors, paper texture visible",
            "Comic Book": "Bold outlines, flat colors, dynamic poses, speech bubble ready",
            "Digital Art": "Modern digital painting style, vibrant colors, fantasy elements ok"
        }
        return style_guides.get(style, "High quality artistic rendering")
    
    def generate_and_save_image(self, prompt: str, output_dir: str, 
                               filename_prefix: str, style: str = "Photorealistic",
                               max_retries: int = 3) -> str:
        """Generate image using OpenAI DALL-E and save to disk"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating image with DALL-E (attempt {attempt + 1}/{max_retries})")
                
                # Generate image using DALL-E 3
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",  # Options: 1024x1024, 1024x1792, 1792x1024
                    quality="standard",  # Options: "standard" or "hd"
                    n=1  # DALL-E 3 only supports n=1
                )
                
                # Get image URL and revised prompt
                image_url = response.data[0].url
                revised_prompt = response.data[0].revised_prompt
                
                # Download and save image
                image_path = self._download_image(image_url, output_dir, filename_prefix)
                
                # Store generation history
                self.generation_history.append({
                    'original_prompt': prompt,
                    'revised_prompt': revised_prompt,
                    'image_path': image_path,
                    'timestamp': time.time(),
                    'style': style
                })
                
                # Save prompt for reference
                prompt_path = os.path.join(output_dir, f"{filename_prefix}_prompt.txt")
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(f"Original Prompt:\n{prompt}\n\n")
                    f.write(f"Revised Prompt (by DALL-E):\n{revised_prompt}\n\n")
                    f.write(f"Style: {style}\n")
                
                logger.info(f"Successfully generated and saved image: {image_path}")
                return image_path
                
            except Exception as e:
                logger.error(f"Error generating image (attempt {attempt + 1}): {str(e)}")
                
                if "rate_limit" in str(e).lower():
                    # Rate limit hit, wait before retry
                    wait_time = min(30 * (attempt + 1), 120)  # Progressive backoff
                    logger.info(f"Rate limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif attempt == max_retries - 1:
                    raise
                else:
                    time.sleep(5)  # Brief pause before retry
        
        raise Exception("Failed to generate image after all retries")
    
    def _download_image(self, url: str, output_dir: str, filename_prefix: str) -> str:
        """Download image from URL and save to disk with robust error handling."""
        try:
            # Use importlib to ensure we get a fresh copy of requests
            import importlib.util
            import sys
            
            # Try to import requests safely
            try:
                # First try to get requests from standard location
                import requests
                # Verify the module has the expected attribute
                if not hasattr(requests, 'get'):
                    raise ImportError("requests module is missing 'get' attribute")
            except (ImportError, AttributeError):
                # If that fails, try to import it directly from pip's vendor directory
                try:
                    import pip._vendor.requests as requests
                except (ImportError, AttributeError):
                    # Last resort: use importlib to force a fresh import
                    spec = importlib.util.find_spec('requests')
                    requests = importlib.util.module_from_spec(spec)
                    sys.modules['requests'] = requests
                    spec.loader.exec_module(requests)
            
            # Make the request with timeout and retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, timeout=30, stream=True)
                    response.raise_for_status()
                    break
                except (requests.RequestException, ConnectionError) as e:
                    if attempt == max_retries - 1:
                        raise Exception(f"Failed to download image after {max_retries} attempts: {str(e)}")
                    time.sleep(1)  # Wait before retry
            
            # Determine file extension
            content_type = response.headers.get('content-type', '').lower()
            if 'png' in content_type:
                ext = 'png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            else:
                # Default to jpg if content type is unknown
                ext = 'jpg'
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Save image with unique filename
            timestamp = int(time.time())
            image_path = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.{ext}")
            
            # Save in chunks to handle large files
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
            
            return image_path
            
        except Exception as e:
            error_msg = f"Error downloading image from {url}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def generate_character_reference(self, character_desc: str, style: str, 
                                   output_dir: str) -> str:
        """Generate a reference image for the character to ensure consistency"""
        
        prompt = f"""Create a character reference sheet in {style.lower()} style.
        
Character: {character_desc}

Show the character in a neutral pose, full body visible, facing forward.
Clear details of face, clothing, and distinguishing features.
White or simple background.
Reference sheet style suitable for maintaining consistency."""

        return self.generate_and_save_image(
            prompt, 
            output_dir, 
            "character_reference",
            style
        )
    
    def estimate_cost(self, num_images: int, quality: str = "standard") -> Dict[str, float]:
        """Estimate the cost of generating images"""
        # DALL-E 3 pricing (as of 2024)
        pricing = {
            "standard": {
                "1024x1024": 0.040,
                "1024x1792": 0.080,
                "1792x1024": 0.080
            },
            "hd": {
                "1024x1024": 0.080,
                "1024x1792": 0.120,
                "1792x1024": 0.120
            }
        }
        
        cost_per_image = pricing.get(quality, {}).get("1024x1024", 0.040)
        total_cost = num_images * cost_per_image
        
        return {
            "cost_per_image": cost_per_image,
            "total_cost": total_cost,
            "num_images": num_images,
            "quality": quality
        }
    
    def save_generation_history(self, output_dir: str):
        """Save the generation history to a JSON file"""
        history_path = os.path.join(output_dir, 'generation_history.json')
        with open(history_path, 'w') as f:
            json.dump(self.generation_history, f, indent=2)
        logger.info(f"Saved generation history to {history_path}")