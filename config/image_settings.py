#!/usr/bin/env python3
"""
Image enhancement settings for GGShot screenshot analysis
"""

# Enhancement levels available to users
ENHANCEMENT_LEVELS = {
    "quick": {
        "name": "Quick",
        "description": "Basic enhancement (fastest)",
        "emoji": "⚡",
        "processing_time": "~1-2 seconds"
    },
    "standard": {
        "name": "Standard",
        "description": "Balanced quality/speed (recommended)",
        "emoji": "⚖️",
        "processing_time": "~2-3 seconds"
    },
    "advanced": {
        "name": "Advanced",
        "description": "Maximum quality (slower)",
        "emoji": "🔬",
        "processing_time": "~3-5 seconds"
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "For very poor quality images",
        "emoji": "🔥",
        "processing_time": "~5-10 seconds"
    }
}

# Default enhancement level
DEFAULT_ENHANCEMENT_LEVEL = "standard"

# Image quality thresholds
IMAGE_QUALITY_THRESHOLDS = {
    "min_width": 800,
    "min_height": 600,
    "mobile_min_width": 600,  # Lower threshold for mobile
    "mobile_min_height": 1000,  # Mobile screenshots are tall
    "blur_threshold": 100,  # Lower values indicate more blur
    "contrast_threshold": 30,  # Standard deviation threshold
    "brightness_range": (85, 170),  # Acceptable brightness range
    "dark_mode_threshold": 50,  # Mean brightness below this = dark mode
    "very_dark_threshold": 30  # Mean brightness below this = very dark
}

# Enhancement parameters
ENHANCEMENT_PARAMS = {
    "quick": {
        "contrast_factor": 1.3,
        "sharpness_factor": 1.2,
        "denoise": False,
        "upscale": False
    },
    "standard": {
        "contrast_factor": 1.4,
        "sharpness_factor": 1.5,
        "denoise": True,
        "upscale": False,
        "edge_enhance": True
    },
    "advanced": {
        "contrast_factor": 1.5,
        "sharpness_factor": 2.0,
        "denoise": True,
        "upscale": True,
        "edge_enhance": True,
        "adaptive_histogram": True
    },
    "aggressive": {
        "contrast_factor": 2.0,
        "sharpness_factor": 2.5,
        "brightness_multiplier": 3.0,  # For very dark images
        "denoise": True,
        "upscale": True,
        "edge_enhance": True,
        "color_reduction": True,  # Reduce color saturation for better text
        "unsharp_mask": True
    }
}

# Multi-pass extraction settings
MULTI_PASS_SETTINGS = {
    "max_attempts": 3,
    "confidence_threshold": 0.8,  # Stop if we reach this confidence
    "enhancement_progression": ["standard", "advanced", "aggressive"],
    "enable_fallback_prompts": True
}

# Mobile screenshot detection
MOBILE_DETECTION = {
    "aspect_ratio_threshold": 0.7,  # width/height ratio below this = mobile
    "min_resolution": (600, 1000),
    "typical_resolutions": [
        (750, 1334),   # iPhone 6/7/8
        (1080, 1920),  # Full HD phones
        (1125, 2436),  # iPhone X/XS
        (828, 1792),   # iPhone XR/11
        (1170, 2532),  # iPhone 12/13 Pro
        (1284, 2778),  # iPhone 12/13 Pro Max
        (591, 1280)    # Common Android
    ]
}