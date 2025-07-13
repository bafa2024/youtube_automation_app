# File: leonardo_generator.py
# Path: /core/leonardo_generator.py

import os
import time
import requests
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class LeonardoImageGenerator:
    """Handles AI image generation using Leonardo AI API"""
    
    BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.generation_history = []
        # Popular Leonardo AI models
        self.model_ids = {
            "Leonardo Diffusion XL": "1e60896f-3c26-4296-8ecc-53e2afecc132",
            "Leonardo Vision XL": "5c232a9e-9061-4777-980a-ddc8e65647c6",
            "Anime Pastel Dream": "1aa0f478-51be-4efd-94e8-76bfc8f533af",
            "3D Animation Style": "d69c8273-6b17-4a30-a13e-d6637ae1c644",
            "PhotoReal": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3"
        }
        
    def create_scene_prompt(self, script_segment: str, character_desc: str, 
                          style: str, scene_number: int) -> str:
        """Create a detailed prompt for Leonardo AI based on script segment"""
        
        # Base prompt structure for consistency
        base_prompt = f"""Scene {scene_number}: {script_segment}

Character: {character_desc}

Style: {style.lower()} style, high quality, detailed
{self._get_style_guidelines(style)}

Important: Maintain exact same character appearance throughout, professional quality suitable for video content"""

        # Add style-specific enhancements for Leonardo AI
        if style == "Cinematic":
            base_prompt += ", cinematic lighting, movie still, film grain, wide angle lens, dramatic composition"
        elif style == "Photorealistic":
            base_prompt += ", ultra realistic, professional photography, natural lighting, 8k quality, sharp focus"
        elif style == "Anime/Manga":
            base_prompt += ", anime art style, vibrant colors, cel shaded, studio quality animation"
        elif style == "3D Render":
            base_prompt += ", 3D rendered, Pixar style, subsurface scattering, ambient occlusion, ray traced"
            
        # Add negative prompt for better quality
        negative_prompt = "blurry, low quality, distorted, deformed, ugly, duplicate, error, out of frame, cropped, low resolution"
        
        return base_prompt, negative_prompt
    
    def _get_style_guidelines(self, style: str) -> str:
        """Get style-specific guidelines for Leonardo AI"""
        style_guides = {
            "Photorealistic": "photorealistic rendering, lifelike textures, realistic proportions, natural environment",
            "Cinematic": "cinematic composition, movie quality, dramatic angles, professional color grading",
            "Anime/Manga": "anime art style, expressive features, clean line art, vibrant anime colors",
            "3D Render": "3D animation style, smooth rendering, professional 3D art, volumetric lighting",
            "Oil Painting": "oil painting style, visible brushstrokes, classical art, rich textures",
            "Watercolor": "watercolor painting, soft blending, artistic style, paper texture",
            "Comic Book": "comic book art, bold outlines, flat colors, dynamic action poses",
            "Digital Art": "digital art style, modern illustration, vibrant colors, detailed artwork"
        }
        return style_guides.get(style, "high quality professional artwork")
    
    def _get_model_id_for_style(self, style: str) -> str:
        """Get the appropriate Leonardo model ID for the style"""
        style_model_map = {
            "Photorealistic": self.model_ids["PhotoReal"],
            "Cinematic": self.model_ids["Leonardo Vision XL"],
            "Anime/Manga": self.model_ids["Anime Pastel Dream"],
            "3D Render": self.model_ids["3D Animation Style"],
            "Digital Art": self.model_ids["Leonardo Diffusion XL"],
            "Oil Painting": self.model_ids["Leonardo Diffusion XL"],
            "Watercolor": self.model_ids["Leonardo Diffusion XL"],
            "Comic Book": self.model_ids["Leonardo Diffusion XL"]
        }
        return style_model_map.get(style, self.model_ids["Leonardo Diffusion XL"])
    
    def generate_and_save_image(self, prompt: str, output_dir: str, 
                               filename_prefix: str, style: str = "Photorealistic",
                               max_retries: int = 3) -> str:
        """Generate image using Leonardo AI and save to disk"""
        
        positive_prompt, negative_prompt = prompt if isinstance(prompt, tuple) else (prompt, "")
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating image with Leonardo AI (attempt {attempt + 1}/{max_retries})")
                
                # Create generation request
                generation_id = self._create_generation(
                    positive_prompt, 
                    negative_prompt,
                    style
                )
                
                # Wait for generation to complete
                image_urls = self._wait_for_generation(generation_id)
                
                if not image_urls:
                    raise Exception("No images generated")
                
                # Download and save the first image
                image_url = image_urls[0]
                image_path = self._download_image(image_url, output_dir, filename_prefix)
                
                # Store generation history
                self.generation_history.append({
                    'prompt': positive_prompt,
                    'negative_prompt': negative_prompt,
                    'generation_id': generation_id,
                    'image_path': image_path,
                    'timestamp': time.time(),
                    'style': style
                })
                
                # Save prompt for reference
                prompt_path = os.path.join(output_dir, f"{filename_prefix}_prompt.txt")
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(f"Positive Prompt:\n{positive_prompt}\n\n")
                    f.write(f"Negative Prompt:\n{negative_prompt}\n\n")
                    f.write(f"Style: {style}\n")
                    f.write(f"Generation ID: {generation_id}")
                
                logger.info(f"Successfully generated and saved image: {image_path}")
                return image_path
                
            except Exception as e:
                logger.error(f"Error generating image (attempt {attempt + 1}): {str(e)}")
                
                if "rate" in str(e).lower() or "limit" in str(e).lower():
                    wait_time = min(30 * (attempt + 1), 120)
                    logger.info(f"Rate limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                elif attempt == max_retries - 1:
                    raise
                else:
                    time.sleep(5)
        
        raise Exception("Failed to generate image after all retries")
    
    def _create_generation(self, prompt: str, negative_prompt: str, style: str) -> str:
        """Create a generation request with Leonardo AI"""
        
        model_id = self._get_model_id_for_style(style)
        
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "modelId": model_id,
            "width": 1024,
            "height": 1024,
            "num_images": 1,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "scheduler": "EULER_DISCRETE",
            "public": False,
            "tiling": False,
            "alchemy": True,  # Enable Alchemy for better quality
            "photoReal": style == "Photorealistic",
            "photoRealStrength": 0.5 if style == "Photorealistic" else None,
            "promptMagic": True,  # Enable prompt enhancement
            "promptMagicVersion": "v3",
            "promptMagicStrength": 0.3
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        response = requests.post(
            f"{self.BASE_URL}/generations",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code != 200:
            error_msg = f"Leonardo API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        data = response.json()
        generation_id = data['sdGenerationJob']['generationId']
        logger.info(f"Created generation request: {generation_id}")
        
        return generation_id
    
    def _wait_for_generation(self, generation_id: str, timeout: int = 180) -> List[str]:
        """Wait for generation to complete and return image URLs"""
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.BASE_URL}/generations/{generation_id}",
                headers=self.headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to check generation status: {response.status_code}")
            
            data = response.json()
            generation = data['generations_by_pk']
            
            if generation['status'] == 'COMPLETE':
                # Extract image URLs
                image_urls = []
                for image in generation['generated_images']:
                    image_urls.append(image['url'])
                return image_urls
            
            elif generation['status'] == 'FAILED':
                raise Exception("Generation failed")
            
            # Still pending, wait a bit
            time.sleep(3)
        
        raise Exception("Generation timeout")
    
    def _download_image(self, url: str, output_dir: str, filename_prefix: str) -> str:
        """Download image from URL and save to disk"""
        response = requests.get(url)
        response.raise_for_status()
        
        # Leonardo AI images are usually JPG
        ext = 'jpg'
        
        # Save image
        image_path = os.path.join(output_dir, f"{filename_prefix}.{ext}")
        with open(image_path, 'wb') as f:
            f.write(response.content)
        
        return image_path
    
    def generate_character_reference(self, character_desc: str, style: str, 
                                   output_dir: str) -> str:
        """Generate a reference image for the character to ensure consistency"""
        
        prompt = f"""Character reference sheet, full body character design:
{character_desc}

Neutral pose, T-pose or standing straight, facing forward, full body visible
Clear view of all features, clothing details, and colors
Simple white background, character model sheet style
Professional character design reference
{style.lower()} style"""

        negative_prompt = "multiple views, multiple poses, action pose, complex background"

        return self.generate_and_save_image(
            (prompt, negative_prompt), 
            output_dir, 
            "character_reference",
            style
        )
    
    def get_user_info(self) -> Dict:
        """Get user information and remaining tokens"""
        
        response = requests.get(
            f"{self.BASE_URL}/me",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get user info: {response.status_code}")
            return {}
    
    def save_generation_history(self, output_dir: str):
        """Save the generation history to a JSON file"""
        history_path = os.path.join(output_dir, 'generation_history.json')
        with open(history_path, 'w') as f:
            json.dump(self.generation_history, f, indent=2)
        logger.info(f"Saved generation history to {history_path}")