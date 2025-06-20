# GGShot Screenshot Enhancement Documentation

## Overview
This document describes the enhanced image processing capabilities added to the GGShot screenshot analysis feature to improve OCR accuracy for low-quality images.

## Key Enhancements

### 1. Multi-Pass OCR Extraction
The system now attempts up to 3 passes with progressively more aggressive enhancement:
- **Pass 1**: Standard enhancement
- **Pass 2**: Advanced enhancement with upscaling
- **Pass 3**: Aggressive enhancement for very poor quality

The system stops early if it achieves confidence >= 0.8.

### 2. Dark Mode Detection and Processing
- Automatically detects TradingView dark mode screenshots (mean brightness < 50)
- Special processing pipeline:
  - Image inversion for better contrast
  - Aggressive brightness adjustment
  - Binary thresholding for crisp text

### 3. Mobile Screenshot Optimization
- Detects mobile screenshots by aspect ratio and resolution
- Applies mobile-specific enhancements:
  - Smart upscaling to improve detail
  - Aggressive sharpening for small text
  - Enhanced contrast for mobile UI elements

### 4. Intelligent TP4 Calculation
When TP4 is null in conservative mode:
- Automatically calculates TP4 as: TP3 + 50% of (TP3 - Entry) distance
- Logs the calculation for transparency
- Continues processing without errors

### 5. Alternative Prompting Strategies
Three prompt strategies for different scenarios:
- **Detailed**: Full analysis with strategy detection
- **Simple**: Focus on visible price numbers only
- **Numbers Only**: Extract all numbers and infer purpose

## Image Quality Thresholds

### Standard Thresholds
- Minimum resolution: 800x600
- Blur score threshold: 100 (lower = more blur)
- Acceptable brightness: 85-170
- Contrast threshold: 30 (std deviation)

### Mobile Thresholds
- Minimum resolution: 600x1000
- Dark mode threshold: brightness < 50
- Very dark threshold: brightness < 30

### Enhancement Levels

#### Quick (1-2 seconds)
- Basic contrast: 1.3x
- Basic sharpness: 1.2x
- No denoising or upscaling

#### Standard (2-3 seconds)
- Auto-contrast with 2% cutoff
- Adaptive brightness adjustment
- Median filter denoising
- Edge enhancement

#### Advanced (3-5 seconds)
- All standard enhancements
- Adaptive histogram equalization
- Intelligent upscaling for low-res
- Unsharp masking

#### Aggressive (5-10 seconds)
- Triple brightness for very dark images
- Double contrast enhancement
- Color saturation reduction
- Heavy edge enhancement
- Forced upscaling to 1024px minimum

## Error Handling

### Graceful Degradation
- If enhancement fails, uses original image
- If OCR fails, tries alternative prompts
- If critical values missing, provides clear error messages

### Validation Bypass
- Users can override validation errors
- System warns about unvalidated parameters
- Allows continuation with partial data

## Performance Considerations

### Processing Time
- Multi-pass adds 5-15 seconds for difficult images
- Caching prevents re-processing same image
- Early exit on high confidence saves time

### Memory Usage
- Images are processed in-place when possible
- Original image kept for multi-pass attempts
- Automatic cleanup after processing

## Usage Examples

### Dark Mobile Screenshot
```
Input: 591x1280, brightness: 21
Pass 1: Standard enhancement - Low confidence
Pass 2: Advanced enhancement - Medium confidence  
Pass 3: Aggressive enhancement - Success!
Result: All parameters extracted with 0.75 confidence
```

### Missing TP4 Handling
```
Input: Conservative strategy, TP4 returns null
TP3: 67,000, Entry: 65,000
Calculated TP4: 68,000 (TP3 + 50% distance)
Result: Trade executes successfully
```

## Best Practices

### For Users
1. Ensure good lighting when taking screenshots
2. Avoid excessive zoom that pixelates text
3. Include all price levels in frame
4. Use landscape mode when possible

### For Developers
1. Check quality_report in results
2. Log extraction_method for debugging
3. Handle validation_errors gracefully
4. Consider confidence scores in UI feedback