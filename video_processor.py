#!/usr/bin/env python3
"""
BMW Drive Recorder Video Processor
Converts TS → MOV, with optional metadata overlay (time & velocity)
"""

import json
import subprocess
import os
import sys
import tempfile

# ——— CONFIGURATION ———

TS_FILE      = "01_Drive_Recorder_Camera_selection_All.ts"                  # Input TS file (BMW recorder video)
JSON_FILE    = "Metadata.json"                      # Metadata JSON file (must contain 'entries')
OUTPUT_FILE  = "Drive_Recorder.mov"    # Name of the output MOV file
SHOW_TEXT    = True                                  # True to overlay time & speed; False to skip text

# ——— Helpers ———

def load_metadata(json_file: str) -> list:
    """
    Load and parse the metadata JSON.
    Expects either a list-of-dicts or single dict containing 'entries'.
    Returns a list of entries.
    """
    with open(json_file, 'r') as f:
        data = json.load(f)
    if isinstance(data, list) and data:
        return data[0].get('entries', [])
    return data.get('entries', [])

def get_video_duration(video_file: str) -> float:
    """Get the duration of the video file in seconds using ffprobe."""
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
        else:
            return None
    except:
        return None

def check_ffmpeg() -> bool:
    """Return True if FFmpeg is installed and available in PATH."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_ffmpeg_instructions():
    """Print instructions for installing FFmpeg on macOS."""
    print("\n❌ FFmpeg not found.")
    print("To install FFmpeg on macOS:")
    print("  1. Install Homebrew if needed:")
    print("     /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
    print("  2. Then install FFmpeg:")
    print("     brew install ffmpeg\n")

def format_time(sec: float) -> str:
    """Convert seconds → 'H:MM:SS.CS' for ASS subtitles."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def create_subtitle_file(entries: list, video_duration: float) -> str:
    """
    Create a temporary ASS subtitle file that overlays time & speed.
    Properly synchronizes metadata with video duration.
    Returns the path to the .ass file.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as tmp:
        tmp.write(
            "[Script Info]\n"
            "Title: BMW Overlay\n"
            "ScriptType: v4.00+\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,1,10,10,30,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n\n"
        )
        
        # Calculate timing - distribute metadata entries across video duration
        if video_duration:
            time_per_entry = video_duration / len(entries)
        else:
            # Fallback: assume 10 entries per second (common for vehicle recorders)
            time_per_entry = 0.1
            video_duration = len(entries) * time_per_entry
        
        # Sample entries to avoid too many overlays (every 30th entry for basic version)
        sample_rate = max(1, min(30, len(entries) // 100))  # At least every 30th, max 100 overlays
        sample_entries = entries[::sample_rate]
        
        for i, entry in enumerate(sample_entries):
            # Calculate timing based on actual position in original array
            actual_index = i * sample_rate
            start_time = actual_index * time_per_entry
            end_time = start_time + (time_per_entry * sample_rate)
            
            st = format_time(start_time)
            et = format_time(end_time)
            
            # Convert km/h → mph
            kmh = entry.get('velocity', 0)
            mph = kmh / 1.60934
            
            # Build overlay text: time & speed  
            text = f"Time: {entry.get('time','')}\\NSpeed: {mph:.1f} mph ({kmh:.1f} km/h)"
            tmp.write(f"Dialogue: 0,{st},{et},Default,,0,0,0,,{text}\n")
        
        return tmp.name

def convert_ts_to_mov(ts_file: str, metadata_entries: list, output_file: str) -> bool:
    """
    Run ffmpeg to convert TS → MOV.
    If SHOW_TEXT is True, overlay time & speed via a properly synchronized .ass file.
    """
    if not check_ffmpeg():
        install_ffmpeg_instructions()
        return False

    print(f"Converting '{ts_file}' → '{output_file}' ...")
    
    # Get video duration for proper synchronization
    video_duration = None
    if SHOW_TEXT:
        video_duration = get_video_duration(ts_file)
        if video_duration:
            print(f"Video duration: {video_duration:.1f} seconds ({video_duration/60:.1f} minutes)")
        else:
            print("⚠️  Could not determine video duration, using metadata timing")
    
    subtitle_path = None

    if SHOW_TEXT:
        subtitle_path = create_subtitle_file(metadata_entries, video_duration)
        vf_arg = ['-vf', f'ass={subtitle_path}']
    else:
        vf_arg = []

    cmd = ['ffmpeg', '-i', ts_file] + vf_arg + [
        '-c:v', 'libx264',        # video codec
        '-c:a', 'aac',            # audio codec
        '-movflags', '+faststart',# optimize for playback
        '-y', output_file         # overwrite if exists
    ]

    print("Running FFmpeg conversion...")
    print("This may take several minutes depending on video size...")
    
    process = subprocess.run(cmd, capture_output=True, text=True)

    # Clean up subtitle file if created
    if subtitle_path:
        try:
            os.remove(subtitle_path)
        except OSError:
            pass

    if process.returncode == 0:
        orig_mb = os.path.getsize(ts_file) / (1024 * 1024)
        new_mb  = os.path.getsize(output_file) / (1024 * 1024)
        print(f"✅ Success: {orig_mb:.1f} MB → {new_mb:.1f} MB")
        return True
    else:
        print("❌ FFmpeg conversion failed:")
        print(process.stderr.strip())
        return False

def main():
    """Main entry point."""
    print("🏎️  BMW Drive Recorder Video Processor")
    print("=" * 50)

    if not os.path.exists(TS_FILE):
        print(f"❌ Error: '{TS_FILE}' not found.")
        sys.exit(1)
    if not os.path.exists(JSON_FILE):
        print(f"❌ Error: '{JSON_FILE}' not found.")
        sys.exit(1)

    try:
        entries = load_metadata(JSON_FILE)
    except Exception as e:
        print(f"❌ Failed to load metadata: {e}")
        sys.exit(1)

    if SHOW_TEXT:
        print(f"\n📋 Metadata entries: {len(entries):,}")
        if entries:
            speeds = [e.get('velocity', 0) for e in entries]
            print(f"   Speed range: {min(speeds):.1f}–{max(speeds):.1f} km/h")
            print(f"   Date range: {entries[0].get('date', '')} to {entries[-1].get('date', '')}")
        print()
    else:
        print("\nℹ️  Overlay text is disabled.\n")

    success = convert_ts_to_mov(TS_FILE, entries, OUTPUT_FILE)
    if success:
        print(f"\n🎉 Output ready: '{OUTPUT_FILE}'")
        print("You can now open this file with QuickTime Player or any video player.")
    else:
        print("\n❌ Processing failed.")

if __name__ == "__main__":
    main()
