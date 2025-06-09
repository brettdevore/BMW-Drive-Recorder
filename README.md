# BMW Drive Recorder Video Processor

This project converts BMW drive recorder files (TS format) to Mac-compatible MOV format with metadata overlay.

## Files Included

- `video_processor.py` - Basic version with simple overlay
- `advanced_video_processor.py` - Advanced version with customizable overlays, cropping, and trimming

## Prerequisites

### Install FFmpeg (Required)

1. **Install Homebrew** (if not already installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install FFmpeg**:
   ```bash
   brew install ffmpeg
   ```

3. **Verify installation**:
   ```bash
   ffmpeg -version
   ```

## Usage

### Option 1: Advanced Processor (Recommended)

```bash
python3 advanced_video_processor.py
```

**Features:**
- Professional overlay styling with customizable fonts (default: SF Pro Display)
- Configurable display options:
  - Speed display (mph and km/h)
  - Date and time stamps
  - GPS coordinates
- Video cropping options:
  - Full video (no crop)
  - Top-left quadrant
  - Top-right quadrant
  - Bottom-left quadrant
  - Bottom-right quadrant
- Video trimming capabilities
- Better timing synchronization
- Progress display during conversion
- Output: `Drive_Recorder_Enhanced_[Q1-4]_[trim].mov`

### Option 2: Basic Processor

```bash
python3 video_processor.py
```

**Features:**
- Simple text overlay
- Basic speed and time display
- Output: `Drive_Recorder.mov`

## Configuration Options (Advanced Processor)

### Display Settings
```python
DISPLAY = {
    'speed':       True,   # Show speed (mph & km/h)
    'date':        False,  # Show date stamp
    'time':        False,  # Show time stamp
    'coordinates': False,  # Show GPS coordinates
}
```

### Video Settings
```python
CROP_QUADRANT = 0  # 0: no crop; 1: top-left; 2: top-right; 3: bottom-left; 4: bottom-right
ENABLE_TRIMMING = False
TRIM_START    = "00:00:00"
TRIM_DURATION = "00:00:00"
```

### Style Settings
```python
FONT_NAME        = "SF Pro Display"   # Font family
FONT_SIZE        = 16                # Base font size (pixels)
SPEED_MULTIPLIER = 1.4               # Speed text size multiplier
```

## What the Scripts Do

1. **Load Metadata**: Parses the metadata entries from your JSON file
2. **Analyze Video**: Determines video duration and optimal timing
3. **Create Overlay**: Generates synchronized subtitle track with:
   - Vehicle speed in mph and km/h
   - Date and time stamps (if enabled)
   - GPS coordinates (if enabled)
4. **Convert Video**: Uses FFmpeg to:
   - Convert TS to MOV format
   - Apply metadata overlay
   - Apply cropping (if configured)
   - Apply trimming (if enabled)
   - Optimize for Mac playback
   - Maintain audio quality


## Output

The converted video will be playable on macOS with:
- QuickTime Player
- VLC Media Player
- Any modern video player

## Troubleshooting

### FFmpeg Not Found
- Make sure Homebrew is installed
- Run `brew install ffmpeg`
- Restart your terminal

### Large File Size
- The original TS file is typically large
- MOV output may be larger due to the overlay
- Conversion preserves video quality

### Slow Conversion
- Processing time depends on video length and computer speed
- The advanced processor shows progress during conversion
- Typical conversion: 15 seconds for a 40 second video

## Technical Details

- **Input Format**: MPEG Transport Stream (.ts)
- **Output Format**: QuickTime Movie (.mov)
- **Video Codec**: H.264 (libx264)
- **Audio Codec**: AAC
- **Overlay Format**: ASS subtitles with custom styling
- **Synchronization**: Metadata distributed across video timeline
