import argparse
from moviepy.editor import *
from PIL import Image as PILImage
import numpy as np
import os
import glob
from lxml import etree as ET
import xml.etree.ElementTree as ET
import cv2
import shutil
import re

parser = argparse.ArgumentParser(description='Create a video from jacket and audio.')
parser.add_argument('folderpaths', type=str, nargs='*', help='Paths to folders containing the audio and image files')
parser.add_argument('--musicdb', '-m', type=str, default='music_db.xml', help='Path to musicdb file')
parser.add_argument('--rootfolder', '-r', type=str, help='Path to root folder containing all song folders')
parser.add_argument('--outputdir', '-o', type=str, default=None, help='Path to output directory (optional)')

args = parser.parse_args()

if args.rootfolder:
    args.folderpaths = []
    for d in os.listdir(args.rootfolder):
        try:
            if os.path.isdir(os.path.join(args.rootfolder, d)) and int(d[:4]) < 9000:
                args.folderpaths.append(os.path.join(args.rootfolder, d))
        except ValueError:
            pass

def get_music_info(music_id, music_db_path):
    try:
        with open(music_db_path, 'r', encoding='shift-jis', errors='replace') as f:
            contents = f.read()
        root = ET.fromstring(contents)
        music = root.find(f"./music[@id='{int(music_id):d}']")
        if music:
            title_name = music.find('./info/title_name').text
            artist_name = music.find('./info/artist_name').text
            return title_name, artist_name
        else:
            print(f"Song ID {music_id} not found in the music database.")
            return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None


def get_sanitized_filename(filename):
    homoglyphs = {
            '\\' : '＼',
            '/' : '⁄',
            ':' : '։',
            '*' : '⁎',
            '?' : '？',
            '"' : '”',
            '<' : '‹',
            '>' : '›',
            '|' : 'ǀ',
        }
    for bad, good in homoglyphs.items():
        filename = filename.replace(bad, good)
    return filename
    
    
def create_video(folderpath, music_db_path, output_directory):
    music_id = os.path.basename(folderpath)[:4]

    title_name, artist_name = get_music_info(music_id, music_db_path)

    if not title_name or not artist_name:
        return

    video_title = f"{artist_name} - {title_name}"
    video_title = get_sanitized_filename(video_title)

    files_in_directory = os.listdir(folderpath)

    audio_file_endings = ['_5m.s3v', '_4i.s3v', '_3e.s3v', '_2a.s3v', '_1n.s3v', '.s3v']
    audio_file = None

    for ending in audio_file_endings:
        audio_file = next((f for f in files_in_directory if f.endswith(ending) and not f.endswith('_pre.s3v')), None)
        if audio_file:
            break

    if not audio_file:
        print(f"No valid audio file found in folder: {folderpath}. Skipping...")
        return

    audio_file_path = os.path.join(folderpath, audio_file)
    audio = AudioFileClip(audio_file_path)

    image_file_patterns = ['*5_b.png', '*4_b.png', '*3_b.png', '*2_b.png', '*1_b.png']
    image_file = None
    for pattern in image_file_patterns:
        image_files = glob.glob(os.path.join(folderpath, pattern))
        if image_files:
            image_file = image_files[0]
            break

    if image_file:
        image = cv2.imread(image_file)
        image_resized = cv2.resize(image, (1080, 1080), interpolation=cv2.INTER_LANCZOS4)
        image_resized = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB)

        img = ImageClip(image_resized)
    else:
        print(f"No image found in folder: {folderpath}")
        exit(1)

    img = img.set_duration(audio.duration)

    img.fps = 24

    video = img.set_audio(audio)

    if output_directory is None:
        script_directory = os.path.dirname(os.path.abspath(__file__))
        output_file_name = os.path.join(script_directory, video_title + ".mp4")
    else:
        output_file_name = os.path.join(output_directory, video_title + ".mp4")

    video.write_videofile(output_file_name, audio_codec="aac")

for folderpath in args.folderpaths:
    create_video(folderpath, args.musicdb, args.outputdir)
