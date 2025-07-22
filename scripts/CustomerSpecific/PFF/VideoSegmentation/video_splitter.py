#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import subprocess
import os
import sys
from pathlib import Path

class VideoSplitter:
    def __init__(self, exchange_file, video_file, output_dir="output"):
        self.exchange_file = exchange_file
        self.video_file = video_file
        self.output_dir = output_dir
        self.frame_rate = 29.97  # Default frame rate, will be detected from video
        
    def detect_frame_rate(self):
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_streams', self.video_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                for stream in data['streams']:
                    if stream['codec_type'] == 'video':
                        fps_str = stream.get('r_frame_rate', '29.97/1')
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            self.frame_rate = float(num) / float(den)
                        else:
                            self.frame_rate = float(fps_str)
                        break
        except Exception as e:
            print(f"Warning: Could not detect frame rate, using default {self.frame_rate}: {e}")
    
    def frames_to_seconds(self, frames):
        return frames / self.frame_rate
    
    def parse_exchange_file(self):
        tree = ET.parse(self.exchange_file)
        root = tree.getroot()
        
        plays = []
        
        for play in root.findall('.//Play'):
            play_number = play.find('PlayNumber')
            play_type = play.find('PlayType')
            quarter = play.find('Quarter')
            down = play.find('Down')
            distance = play.find('Distance')
            
            play_info = {
                'play_number': play_number.text if play_number is not None else 'Unknown',
                'play_type': play_type.text if play_type is not None else 'Unknown',
                'quarter': quarter.text if quarter is not None else '0',
                'down': down.text if down is not None else '0',
                'distance': distance.text if distance is not None else '0',
                'views': []
            }
            
            for view in play.findall('.//View'):
                mark_in = view.find('MarkIn')
                duration = view.find('Duration')
                camera_view = view.find('CameraView')
                
                if mark_in is not None and duration is not None:
                    view_info = {
                        'mark_in_frames': int(mark_in.text),
                        'duration_frames': int(duration.text),
                        'camera_view': camera_view.text if camera_view is not None else 'Unknown',
                        'start_seconds': self.frames_to_seconds(int(mark_in.text)),
                        'duration_seconds': self.frames_to_seconds(int(duration.text))
                    }
                    play_info['views'].append(view_info)
            
            if play_info['views']:  # Only add plays that have timing information
                plays.append(play_info)
        
        return plays
    
    def split_video(self, plays):
        os.makedirs(self.output_dir, exist_ok=True)
        
        for i, play in enumerate(plays):
            play_num = play['play_number']
            quarter = play['quarter']
            
            for j, view in enumerate(play['views']):
                start_time = view['start_seconds']
                duration = view['duration_seconds']
                camera = view['camera_view']
                
                # Create descriptive filename
                play_num_int = int(play_num) if play_num.isdigit() else 0
                output_filename = f"Play_{play_num_int:02d}_Q{quarter}_{camera}_View{j+1}.mp4"
                output_path = os.path.join(self.output_dir, output_filename)
                
                # FFmpeg command to extract the segment
                cmd = [
                    'ffmpeg', '-i', self.video_file,
                    '-ss', str(start_time),
                    '-t', str(duration),
                    '-c', 'copy',  # Copy streams without re-encoding for speed
                    '-avoid_negative_ts', 'make_zero',
                    '-y',  # Overwrite output files
                    output_path
                ]
                
                print(f"Extracting: {output_filename} (Start: {start_time:.2f}s, Duration: {duration:.2f}s)")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"Error extracting {output_filename}: {result.stderr}")
                    else:
                        print(f"Successfully created: {output_filename}")
                except Exception as e:
                    print(f"Exception while processing {output_filename}: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python video_splitter.py <exchange_file> <video_file>")
        print("Example: python video_splitter.py 'file.xchange' 'file.mp4'")
        sys.exit(1)
    
    exchange_file = sys.argv[1]
    video_file = sys.argv[2]
    
    if not os.path.exists(exchange_file):
        print(f"Error: Exchange file '{exchange_file}' not found")
        sys.exit(1)
    
    if not os.path.exists(video_file):
        print(f"Error: Video file '{video_file}' not found")
        sys.exit(1)
    
    splitter = VideoSplitter(exchange_file, video_file)
    
    print("Detecting video frame rate...")
    splitter.detect_frame_rate()
    print(f"Using frame rate: {splitter.frame_rate} fps")
    
    print("Parsing exchange file...")
    plays = splitter.parse_exchange_file()
    print(f"Found {len(plays)} plays with timing information")
    
    total_views = sum(len(play['views']) for play in plays)
    print(f"Total video segments to extract: {total_views}")
    
    if total_views == 0:
        print("No video segments found to extract")
        sys.exit(1)
    
    print("\nStarting video splitting...")
    splitter.split_video(plays)
    print("\nVideo splitting completed!")

if __name__ == "__main__":
    main()