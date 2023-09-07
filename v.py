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
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


parser = argparse.ArgumentParser(description='Create a video from jacket and audio.')
parser.add_argument('folderpaths', type=str, nargs='*', help='Paths to folders containing the audio and image files')
parser.add_argument('--musicdb', '-m', type=str, default='music_db.xml', help='Path to musicdb file')
parser.add_argument('--rootfolder', '-r', type=str, help='Path to root folder containing all song folders')
parser.add_argument('--outputdir', '-o', type=str, default=None, help='Path to output directory (optional)')
parser.add_argument('--upload', '-u', action='store_true', help='Upload to youtube or not')
parser.add_argument('--client_json', '-c', type=str, default='client.json', help='Path to client_secrets.json file')

args = parser.parse_args()

def get_youtube_service(client_json_path):
    flow = InstalledAppFlow.from_client_secrets_file(client_json_path, ['https://www.googleapis.com/auth/youtube.upload'])
    credentials = flow.run_local_server(port=0)
    youtube = build('youtube', 'v3', credentials=credentials)
    return youtube

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
            version = int(music.find('./info/version').text)
            
            version_dict = {
                1: "BOOTH",
                2: "INFINITE INFECTION",
                3: "GRAVITY WARS",
                4: "HEAVENLY HAVEN",
                5: "VIVID WAVE",
                6: "EXCEED GEAR",
                7: "???",
                8: "???"
            }
            
            version_title = version_dict.get(version, f"Version {version}")
            return title_name, artist_name, version_title
        else:
            print(f"Song ID {music_id} not found in musicdb.")
            return None, None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None



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
            '頽' : 'ä',
            '齷' : 'é',
            '齶' : '♡',
            '驩' : 'Ø',
            '骭' : 'ü',
            '餮' : 'Ƶ',
            '黻' : '⁎',
            '罇' : 'ê',
            '曦' : 'à',
            '曩' : 'è',
            '盥' : '⚙',
            '闃' : 'Ā',
            '煢' : 'ø',
            '蔕' : 'ῦ',
            '雋' : 'Ǜ',
            '鬻' : '♃',
            '鬥' : 'Ã',
            '鬆' : 'Ý',
        }
    for bad, good in homoglyphs.items():
        filename = filename.replace(bad, good)
    return filename
    
    
def create_video(folderpath, music_db_path, output_directory, youtube):
    music_id = os.path.basename(folderpath)[:4]

    title_name, artist_name, version_title = get_music_info(music_id, music_db_path)

    if not title_name or not artist_name or not version_title: 
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
    
    if youtube:
        try:
            request = youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": video_title,
                        "description": f"Composed by {artist_name}, from SDVX {version_title}\n\nSOUND VOLTEX\nhttps://p.eagate.573.jp/game/sdvx/\n© Konami Amusement",
                        "tags": ["sdvx"],
                        "categoryId": "10"
                    },
                    "status": {
                        "privacyStatus": "unlisted",
                        "selfDeclaredMadeForKids": False 
                    }
                },
                media_body=MediaFileUpload(output_file_name)
            )
            response = request.execute()
            print(f"Video '{video_title}' upload done: https://www.youtube.com/watch?v={response['id']}") 
        except HttpError as e:
            print(f"Error occurred: {e}")

def main():
    args = parser.parse_args()
    
    youtube_service = None
    if args.upload:
        youtube_service = get_youtube_service(args.client_json)
        
    for folderpath in args.folderpaths:
        create_video(folderpath, args.musicdb, args.outputdir, youtube_service)
        
if __name__ == "__main__":
    main()