#!/usr/bin/env python3
"""
Advanced image enhancement for GGShot screenshot analysis.
Improves OCR accuracy by applying various image processing techniques.
"""
import logging
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import Optional, Tuple, Dict, Any
import io

logger = logging.getLogger(__name__)

class ImageEnhancer:
    """Advanced image enhancement for trading screenshots"""
    
    def __init__(self):
        self.min_recommended_width = 800
        self.min_recommended_height = 600
        self.target_dpi = 300
        
    def enhance_for_ocr(self, image: Image.Image, level: str = "standard") -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Enhance image for better OCR results
        
        Args:
            image: Input PIL Image
            level: Enhancement level - "quick", "standard", or "advanced"
            
        Returns:
            Tuple of (enhanced_image, quality_report)
        """
        quality_report = self._assess_image_quality(image)
        
        # Apply enhancements based on level
        if level == "quick":
            enhanced = self._quick_enhance(image)
        elif level == "standard":
            enhanced = self._standard_enhance(image)
        elif level == "advanced":
            enhanced = self._advanced_enhance(image)
        else:
            enhanced = self._standard_enhance(image)
            
        quality_report["enhancement_level"] = level
        return enhanced, quality_report
    
    def _assess_image_quality(self, image: Image.Image) -> Dict[str, Any]:
        """Assess image quality and provide recommendations"""
        width, height = image.size
        
        report = {
            "resolution": f"{width}x{height}",
            "is_low_res": width < self.min_recommended_width or height < self.min_recommended_height,
            "aspect_ratio": round(width / height, 2),
            "mode": image.mode,
            "has_transparency": image.mode in ('RGBA', 'LA', 'PA'),
        }
        
        # Analyze brightness and contrast
        gray = image.convert('L')
        pixels = np.array(gray)
        
        report["brightness"] = {
            "mean": int(np.mean(pixels)),
            "std": int(np.std(pixels)),
            "is_dark": np.mean(pixels) < 85,
            "is_bright": np.mean(pixels) > 170,
            "has_low_contrast": np.std(pixels) < 30
        }
        
        # Detect blur (using Laplacian variance)
        report["blur_score"] = self._calculate_blur_score(gray)
        report["is_blurry"] = report["blur_score"] < 100
        
        return report
    
    def _calculate_blur_score(self, gray_image: Image.Image) -> float:
        """Calculate blur score using Laplacian variance"""
        try:
            # Apply Laplacian filter
            edges = gray_image.filter(ImageFilter.FIND_EDGES)
            pixels = np.array(edges)
            
            # Calculate variance - higher variance means sharper image
            variance = np.var(pixels)
            return float(variance)
        except Exception as e:
            logger.error(f"Error calculating blur score: {e}")
            return 100.0  # Default to non-blurry
    
    def _quick_enhance(self, image: Image.Image) -> Image.Image:
        """Quick enhancement - basic adjustments only"""
        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Basic contrast and sharpness
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.3)
        
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        return image
    
    def _standard_enhance(self, image: Image.Image) -> Image.Image:
        """Standard enhancement - moderate processing"""
        # Convert to RGB
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Auto-contrast
        image = ImageOps.autocontrast(image, cutoff=2)
        
        # Adaptive enhancement based on image analysis
        gray = image.convert('L')
        pixels = np.array(gray)
        mean_brightness = np.mean(pixels)
        
        # Brightness adjustment if needed
        if mean_brightness < 85:  # Dark image
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.3)
        elif mean_brightness > 170:  # Bright image
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(0.85)
        
        # Contrast enhancement
        enhancer = ImageEnhance.Contrast(image)
        contrast_factor = 1.4 if np.std(pixels) < 40 else 1.2
        image = enhancer.enhance(contrast_factor)
        
        # Denoise while preserving edges
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.5)
        
        # Edge enhancement for text
        image = image.filter(ImageFilter.EDGE_ENHANCE)
        
        return image
    
    def _advanced_enhance(self, image: Image.Image) -> Image.Image:
        """Advanced enhancement - full processing pipeline"""
        # Start with standard enhancements
        image = self._standard_enhance(image)
        
        # Convert to numpy for advanced processing
        img_array = np.array(image)
        
        # Apply CLAHE-like enhancement
        if len(img_array.shape) == 3:  # Color image
            # Process each channel separately
            for i in range(3):
                channel = img_array[:, :, i]
                channel = self._apply_adaptive_histogram(channel)
                img_array[:, :, i] = channel
        else:  # Grayscale
            img_array = self._apply_adaptive_histogram(img_array)
        
        # Convert back to PIL Image
        image = Image.fromarray(img_array)
        
        # Upscale if image is low resolution
        width, height = image.size
        if width < self.min_recommended_width or height < self.min_recommended_height:
            scale_factor = max(
                self.min_recommended_width / width,
                self.min_recommended_height / height
            )
            new_size = (int(width * scale_factor), int(height * scale_factor))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Final sharpening pass
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        
        return image
    
    def _apply_adaptive_histogram(self, channel: np.ndarray) -> np.ndarray:
        """Apply adaptive histogram equalization to a single channel"""
        # Normalize to 0-255 range
        channel = np.clip(channel, 0, 255).astype(np.uint8)
        
        # Simple adaptive histogram equalization
        # Divide into tiles and equalize each
        h, w = channel.shape
        tile_size = 64
        
        # Process in tiles
        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                y_end = min(y + tile_size, h)
                x_end = min(x + tile_size, w)
                
                tile = channel[y:y_end, x:x_end]
                if tile.size > 0:
                    # Equalize histogram for this tile
                    hist, bins = np.histogram(tile.flatten(), 256, [0, 256])
                    cdf = hist.cumsum()
                    cdf_normalized = cdf * 255 / cdf[-1]
                    
                    # Apply mapping
                    tile_eq = np.interp(tile.flatten(), bins[:-1], cdf_normalized)
                    channel[y:y_end, x:x_end] = tile_eq.reshape(tile.shape)
        
        return channel
    
    def enhance_tradingview_screenshot(self, image: Image.Image) -> Image.Image:
        """Special enhancement for TradingView screenshots with dark mode support"""
        # Detect if this is a dark mode screenshot
        is_dark_mode = self._is_dark_mode_screenshot(image)
        
        if is_dark_mode:
            logger.info("Detected TradingView dark mode screenshot")
            image = self._enhance_dark_mode_screenshot(image)
        else:
            # Apply standard enhancement first
            image = self._standard_enhance(image)
        
        # TradingView-specific optimizations
        # Enhance contrast for price labels (usually on edges)
        width, height = image.size
        
        # Create mask for edge regions where price labels typically are
        mask = Image.new('L', (width, height), 0)
        pixels = mask.load()
        
        # Mark edge regions (where price labels typically are)
        edge_width = int(width * 0.15)
        edge_height = int(height * 0.15)
        
        for x in range(width):
            for y in range(height):
                if x < edge_width or x > width - edge_width or y < edge_height or y > height - edge_height:
                    pixels[x, y] = 255
        
        # Apply stronger enhancement to edge regions
        edge_enhanced = image.copy()
        enhancer = ImageEnhance.Contrast(edge_enhanced)
        edge_enhanced = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Sharpness(edge_enhanced)
        edge_enhanced = enhancer.enhance(2.0)
        
        # Composite the enhanced edges back
        image = Image.composite(edge_enhanced, image, mask)
        
        return image
    
    def _is_dark_mode_screenshot(self, image: Image.Image) -> bool:
        """Detect if screenshot is in dark mode"""
        gray = image.convert('L')
        pixels = np.array(gray)
        mean_brightness = np.mean(pixels)
        
        # Dark mode typically has mean brightness < 50
        return mean_brightness < 50
    
    def _enhance_dark_mode_screenshot(self, image: Image.Image) -> Image.Image:
        """Special enhancement for dark mode TradingView screenshots"""
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # First, significantly brighten the image
        enhancer = ImageEnhance.Brightness(image)
        brightened = enhancer.enhance(3.5)  # Strong brightening
        
        # Apply gamma correction
        img_array = np.array(brightened)
        gamma = 2.0
        img_array = np.power(img_array / 255.0, 1.0 / gamma) * 255.0
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        brightened = Image.fromarray(img_array)
        
        # Now invert for better contrast
        inverted = ImageOps.invert(brightened)
        
        # Apply auto-contrast to the inverted image
        inverted = ImageOps.autocontrast(inverted, cutoff=0)
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(inverted)
        inverted = enhancer.enhance(2.0)
        
        # Sharpen
        enhancer = ImageEnhance.Sharpness(inverted)
        inverted = enhancer.enhance(2.0)
        
        # Apply edge enhancement
        inverted = inverted.filter(ImageFilter.EDGE_ENHANCE_MORE)
        
        # For very dark images, try to preserve more detail
        gray = inverted.convert('L')
        pixels = np.array(gray)
        
        # Adaptive thresholding based on image statistics
        mean_val = np.mean(pixels)
        std_val = np.std(pixels)
        threshold = int(mean_val - 0.5 * std_val)
        threshold = max(80, min(180, threshold))  # Keep threshold in reasonable range
        
        # Apply threshold to create high contrast black and white image
        bw = gray.point(lambda x: 0 if x < threshold else 255, 'L')
        
        # Convert back to RGB
        return bw.convert('RGB')
    
    def prepare_for_ocr(self, image: Image.Image, target_regions: Optional[list] = None) -> Image.Image:
        """
        Prepare image specifically for OCR processing
        
        Args:
            image: Input image
            target_regions: Optional list of (x, y, width, height) tuples for regions to focus on
        """
        # Convert to grayscale for better OCR
        gray = image.convert('L')
        
        # Apply binary threshold to make text stand out
        threshold = 128
        gray = gray.point(lambda x: 255 if x > threshold else 0, mode='1')
        
        # Convert back to RGB for consistency
        image = gray.convert('RGB')
        
        return image
    
    def enhance_mobile_screenshot(self, image: Image.Image) -> Image.Image:
        """Special enhancement for mobile screenshots (typically lower resolution)"""
        width, height = image.size
        
        # Mobile screenshots are typically portrait
        is_mobile = height > width and (width < 800 or height < 1400)
        
        if not is_mobile:
            return self._standard_enhance(image)
        
        logger.info(f"Detected mobile screenshot: {width}x{height}")
        
        # Convert to RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Upscale first to improve detail
        target_width = max(1024, width)
        scale_factor = target_width / width
        new_size = (int(width * scale_factor), int(height * scale_factor))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Apply denoising
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        # Auto-contrast with aggressive cutoff
        image = ImageOps.autocontrast(image, cutoff=3)
        
        # Enhance brightness for mobile screenshots (often darker)
        gray = image.convert('L')
        pixels = np.array(gray)
        mean_brightness = np.mean(pixels)
        
        if mean_brightness < 100:
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.5)
        
        # Strong contrast enhancement
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.8)
        
        # Aggressive sharpening for text
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=2))
        
        # Edge enhancement
        image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)
        
        return image

# Global enhancer instance
image_enhancer = ImageEnhancer()

def enhance_screenshot(image: Image.Image, level: str = "standard") -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Convenience function to enhance screenshot
    
    Args:
        image: PIL Image to enhance
        level: Enhancement level ("quick", "standard", "advanced")
        
    Returns:
        Tuple of (enhanced_image, quality_report)
    """
    return image_enhancer.enhance_for_ocr(image, level)

def enhance_tradingview(image: Image.Image) -> Image.Image:
    """
    Convenience function for TradingView-specific enhancement
    
    Args:
        image: PIL Image of TradingView screenshot
        
    Returns:
        Enhanced image
    """
    return image_enhancer.enhance_tradingview_screenshot(image)

def enhance_mobile(image: Image.Image) -> Image.Image:
    """
    Convenience function for mobile screenshot enhancement
    
    Args:
        image: PIL Image of mobile screenshot
        
    Returns:
        Enhanced image optimized for mobile screenshots
    """
    return image_enhancer.enhance_mobile_screenshot(image)