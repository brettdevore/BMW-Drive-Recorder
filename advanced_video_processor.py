#!/usr/bin/env python3
"""Convert TS → MOV with synchronized metadata overlay for BMW Drive Recorder."""

import json
import subprocess
import os
import sys
import tempfile
from datetime import datetime

# ——— CONFIGURATION ———

# Input TS file (BMW recorder video)
TS_FILE = "01_Drive_Recorder_Camera_selection_All.ts"       # BMW recorder video file

# Metadata JSON file with GPS, speed, date/time data
JSON_FILE = "Metadata.json"                                # Metadata file

# Which quadrant to crop (0 = full; 1–4 = quadrants)
CROP_QUADRANT = 1                                          # 0: no crop; 1: top-left; 2: top-right; 3: bottom-left; 4: bottom-right

# Display flags for overlay components
DISPLAY = {
    'speed':       True,   # Show speed (mph & km/h)
    'date':        False,  # Show date stamp
    'time':        False,  # Show time stamp
    'coordinates': False,  # Show GPS coordinates
}

# Video trimming configuration
ENABLE_TRIMMING = False             # Enable trimming of input video
TRIM_START    = "00:00:00"         # Trim start time (HH:MM:SS or seconds)
TRIM_DURATION = "00:00:00"         # Trim duration (HH:MM:SS or seconds)

# Font & style for ASS subtitles
FONT_NAME        = "SF Pro Display"   # Font family
FONT_SIZE        = 16                # Base font size (pixels)
SPEED_MULTIPLIER = 1.4               # Speed text size = FONT_SIZE * SPEED_MULTIPLIER
PRIMARY_COLOR    = "&H00FFFFFF"      # Text color (white) in ASS hex format
SECONDARY_COLOR  = "&H000000FF"      # Secondary color (red) in ASS hex format
OUTLINE_COLOR    = "&H00000000"      # Outline color (black) in ASS hex format
BACK_COLOR       = "&H80000000"      # Background color (semi-transparent black)

# Combined ASS style template; we'll override 'MarginV' per‐style
ASS_STYLE = {
    'Fontname':       FONT_NAME,       # Font family name
    'Fontsize':       FONT_SIZE,       # Font size in pixels
    'PrimaryColour':  PRIMARY_COLOR,   # Primary text color
    'SecondaryColour': SECONDARY_COLOR,# Secondary text color
    'OutlineColour':  OUTLINE_COLOR,   # Outline color for text
    'BackColour':     BACK_COLOR,      # Background box color
    'Bold':           1,               # Bold on (1) / off (0)
    'Italic':         0,               # Italic on (1) / off (0)
    'Underline':      0,               # Underline on (1) / off (0)
    'StrikeOut':      0,               # Strikeout on (1) / off (0)
    'ScaleX':         100,             # Horizontal scaling percentage
    'ScaleY':         100,             # Vertical scaling percentage
    'Spacing':        0,               # Character spacing (0 = normal)
    'Angle':          0,               # Text rotation angle (degrees)
    'BorderStyle':    1,               # 1 = opaque box; 0 = outline+shadow
    'Outline':        1,               # Outline thickness (pixels)
    'Shadow':         2,               # Drop shadow depth (pixels)
    'Alignment':      1,               # Text alignment (1 = bottom-left, etc.)
    'MarginL':        20,              # Left margin (pixels)
    'MarginR':        20,              # Right margin (pixels)
    'MarginV':        None,            # Vertical margin (set per-style)
    'Encoding':       1,               # Text encoding (1 = default)
}

# ——— Helpers ———

def format_time(sec: float) -> str:
    """Convert seconds → 'H:MM:SS.CS' for ASS timestamps."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def generate_output_filename() -> str:
    """
    Create an output filename reflecting crop quadrant and trim options.
    Example: Drive_Recorder_Enhanced_Q1_trim_000015_000010.mov
    """
    quadrant = "full" if CROP_QUADRANT == 0 else f"Q{CROP_QUADRANT}"
    trim = ""
    if ENABLE_TRIMMING:
        # Remove colons and dots for filename cleanliness
        clean = lambda t: t.replace(":", "").replace(".", "")
        trim = f"_trim_{clean(TRIM_START)}_{clean(TRIM_DURATION)}"
    return f"Drive_Recorder_Enhanced_{quadrant}{trim}.mov"

OUTPUT_FILE = generate_output_filename()

def check_dependencies() -> bool:
    """Ensure ffmpeg and ffprobe are installed on the system."""
    missing = []
    for tool in ('ffmpeg', 'ffprobe'):
        try:
            subprocess.run([tool, '-version'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool)
    if missing:
        print(f"❌ Missing required tools: {', '.join(missing)}")
        print("   Install via Homebrew: brew install ffmpeg")
        return False
    return True

def load_metadata(filepath: str):
    """
    Parse metadata JSON; return a tuple (entries_list, VIN).
    Supports either a list-of-dicts or single-dict format.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    if isinstance(data, list) and data:
        entries = data[0].get('entries', [])
        vin     = data[0].get('VIN', 'Unknown')
    else:
        entries = data.get('entries', [])
        vin     = data.get('VIN', 'Unknown')
    return entries, vin

def get_video_duration(ts_path: str) -> float:
    """
    Use ffprobe to obtain video duration (seconds).
    Raises RuntimeError if ffprobe fails.
    """
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', ts_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("ffprobe failed to read video duration.")
    info = json.loads(result.stdout)
    return float(info['format']['duration'])

def create_metadata_overlay(entries: list, duration: float, vin: str) -> str:
    """
    Write a temporary .ass subtitle file that shows speed/date/time/GPS.
    Returns the path to the generated .ass file.
    """
    count = len(entries)

    # If we couldn't get a valid duration, assume 10 entries per second
    if duration <= 0:
        duration     = count * 0.1
        time_per_sub = 0.1
    else:
        time_per_sub = duration / count

    # Limit to 1000 subtitle lines by sampling every 'step' entries
    max_subs = 1000
    step     = max(1, count // max_subs)
    sampled  = entries[::step]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as tmp:
        # Write ASS header
        header = [
            "[Script Info]",
            f"Title: BMW Drive Recorder – VIN: {vin}",
            "ScriptType: v4.00+",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
            "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding",
        ]

        # Speed style (larger font, margin near bottom)
        ASS_STYLE['Fontsize'] = int(FONT_SIZE * SPEED_MULTIPLIER)
        ASS_STYLE['MarginV']  = 30  # Vertical margin for speed text
        speed_vals = ",".join(str(ASS_STYLE[key]) for key in (
            'Fontname','Fontsize','PrimaryColour','SecondaryColour','OutlineColour',
            'BackColour','Bold','Italic','Underline','StrikeOut','ScaleX','ScaleY',
            'Spacing','Angle','BorderStyle','Outline','Shadow','Alignment','MarginL',
            'MarginR','MarginV','Encoding'
        ))
        header.append(f"Style: Speed,{speed_vals}")

        # Info style (normal font, margin slightly higher)
        ASS_STYLE['Fontsize'] = FONT_SIZE
        ASS_STYLE['MarginV']  = 60  # Vertical margin for info text
        info_vals = ",".join(str(ASS_STYLE[key]) for key in (
            'Fontname','Fontsize','PrimaryColour','SecondaryColour','OutlineColour',
            'BackColour','Bold','Italic','Underline','StrikeOut','ScaleX','ScaleY',
            'Spacing','Angle','BorderStyle','Outline','Shadow','Alignment','MarginL',
            'MarginR','MarginV','Encoding'
        ))
        header.append(f"Style: Info,{info_vals}")
        header.append("")
        header.append("[Events]")
        header.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
        header.append("")

        tmp.write("\n".join(header) + "\n")

        # Write subtitle lines for each sampled entry
        for idx, entry in enumerate(sampled):
            actual_idx = idx * step
            start_sec  = actual_idx * time_per_sub
            end_sec    = min(duration, (actual_idx + step) * time_per_sub)

            st = format_time(start_sec)
            et = format_time(end_sec)

            lines = []
            # Speed overlay (if enabled)
            if DISPLAY['speed']:
                kmh = entry.get('velocity', 0)
                mph = kmh / 1.60934
                speed_txt = f"{mph:.1f} mph ({kmh:.1f} km/h)"
                lines.append(("Speed", speed_txt))

            # Date/time overlay
            info_parts = []
            if DISPLAY['date'] and DISPLAY['time']:
                info_parts.append(f"{entry.get('date','')} @ {entry.get('time','')}")
            elif DISPLAY['date']:
                info_parts.append(f"Date: {entry.get('date','')}")
            elif DISPLAY['time']:
                info_parts.append(f"Time: {entry.get('time','')}")

            # GPS coordinates overlay
            if DISPLAY['coordinates']:
                lat = entry.get('latitude', 0.0)
                lon = entry.get('longitude', 0.0)
                info_parts.append(f"GPS: {lat:.6f}, {lon:.6f}")

            if info_parts:
                info_txt = "\\N".join(info_parts)
                lines.append(("Info", info_txt))

            for style, text in lines:
                tmp.write(f"Dialogue: 0,{st},{et},{style},,0,0,0,,{text}\\n\n")

        return tmp.name

def convert_with_overlay(ts_path: str, entries: list, vin: str, out_path: str) -> bool:
    """
    Run ffmpeg to crop (if requested), trim (if enabled), overlay subtitles,
    and produce the final .mov output.
    """
    print(f"🔨 Converting '{ts_path}' → '{out_path}' …")
    try:
        duration = get_video_duration(ts_path)
    except Exception as e:
        print(f"⚠️  Could not read duration: {e}")
        duration = 0

    subtitle_file = create_metadata_overlay(entries, duration, vin)

    # Build ffmpeg video filter chain: crop → subtitles
    filters = []
    if CROP_QUADRANT in (1, 2, 3, 4):
        crops = {
            1: "crop=in_w/2:in_h/2:0:0",
            2: "crop=in_w/2:in_h/2:in_w/2:0",
            3: "crop=in_w/2:in_h/2:0:in_h/2",
            4: "crop=in_w/2:in_h/2:in_w/2:in_h/2",
        }
        filters.append(crops[CROP_QUADRANT])

    filters.append(f"ass={subtitle_file}")
    vf = ",".join(filters)

    cmd = ['ffmpeg', '-i', ts_path]

    if ENABLE_TRIMMING:
        cmd += ['-ss', TRIM_START, '-t', TRIM_DURATION]

    cmd += [
        '-vf', vf,
        '-c:v', 'libx264',       # Video codec
        '-preset', 'veryslow',   # Encoding preset (slower but high quality)
        '-crf', '1',             # CRF=1 → near‐lossless quality
        '-c:a', 'aac',           # Audio codec
        '-b:a', '128k',          # Audio bitrate
        '-movflags', '+faststart', # Optimize for streaming
        '-y', out_path
    ]

    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    for line in process.stderr:
        if 'time=' in line:
            print(f"\r{line.strip()}", end="", flush=True)
    process.wait()
    print()  # newline after progress

    # Delete the temporary subtitle file
    try:
        os.remove(subtitle_file)
    except OSError:
        pass

    if process.returncode == 0:
        before = os.path.getsize(ts_path) / (1024 * 1024)
        after  = os.path.getsize(out_path) / (1024 * 1024)
        change = (after - before) / before * 100 if before > 0 else 0
        print(f"✅ Done! Size: {before:.1f} MB → {after:.1f} MB ({change:+.1f} %)")
        return True
    else:
        print(f"❌ FFmpeg failed (exit code {process.returncode})")
        return False

# ——— Main Entry Point ———

def main():
    print("🛠️  BMW Drive Recorder Processor")
    if not check_dependencies():
        sys.exit(1)

    if not os.path.exists(TS_FILE):
        print(f"❌ '{TS_FILE}' not found. Exiting.")
        sys.exit(1)
    if not os.path.exists(JSON_FILE):
        print(f"❌ '{JSON_FILE}' not found. Exiting.")
        sys.exit(1)

    try:
        entries, vin = load_metadata(JSON_FILE)
    except Exception as e:
        print(f"❌ Failed to load metadata: {e}")
        sys.exit(1)

    print(f"📋 Metadata: VIN={vin}, entries={len(entries):,}")
    if entries:
        first, last = entries[0], entries[-1]
        print(f"   Date range: {first.get('date')} → {last.get('date')}")
        speeds = [e.get('velocity', 0) for e in entries]
        print(f"   Speed range: {min(speeds):.1f}–{max(speeds):.1f} km/h")

    print("\n🎬 Starting conversion…")
    success = convert_with_overlay(TS_FILE, entries, vin, OUTPUT_FILE)
    if success:
        print(f"\n🎉 Your file is ready: '{OUTPUT_FILE}' (playable in QuickTime).")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
