import argparse
from moviepy.editor import *
from PIL import Image as PILImage
import numpy as np
import os
import glob
import xml.etree.ElementTree as ET
import cv2
import shutil
import re
import subprocess
from pydub import AudioSegment

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
        with open(music_db_path, 'r', encoding='ms932', errors='replace') as f:
            contents = f.read()
        root = ET.fromstring(contents)
        music = root.find(f"./music[@id='{int(music_id):d}']")
        if music:
            title_name = music.find('./info/title_name').text
            artist_name = music.find('./info/artist_name').text
            inf_ver = music.find('./info/inf_ver')
            inf_ver_value = int(inf_ver.text) if inf_ver is not None and inf_ver.text.isdigit() else 1
            return title_name, artist_name, inf_ver_value
        else:
            print(f"Song ID {music_id} not found.")
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
            '躔' : '🐾',
            '釁' : '🍄',
            '蹙' : 'ℱ',
            '鬮' : '¡',
            '隍' : 'Ü',
            '龕' : '€',
            '趁' : 'Ǣ',
            '彜' : 'ū',
            '騫' : 'á',
            '鬯' : 'ī',
            '瑟' : 'ō',
            '黷' : 'ē',
            '齣' : 'Ú',
            '齧' : 'Ä',
            '霻' : '♠',
            '齪' : '♣',
            '鑈' : '♦',
            '齲' : '♥',
            '驫' : 'ā',
            '饌' : '²',
            '鑷' : 'ゔ',
        }
    
    for bad, good in homoglyphs.items():
        filename = filename.replace(bad, good)
    return filename

def create_video(folderpath, music_db_path, output_directory):
    music_id = os.path.basename(folderpath)[:4]

    title_name, artist_name, inf_ver = get_music_info(music_id, music_db_path)

    if not title_name or not artist_name:
        return

    files_in_directory = os.listdir(folderpath)
    image_file_patterns = ['*5_b.png', '*4_b.png', '*3_b.png', '*2_b.png', '*1_b.png']

    special_cases = {
        "_5m.s3v": "[MXM]",
        "_3e.s3v": "[EXH]",
        "_2a.s3v": "[ADV]",
        "_1n.s3v": "[NOV]",
    }

    inf_cases = {
        2: "[INF]",
        3: "[GRV]",
        4: "[HVN]",
        5: "[VVD]",
        6: "[XCD]"
    }

    def find_audio_and_jacket(suffix, jacket_suffix):
        audio_file = next((f for f in files_in_directory if re.search(suffix, f) and not re.search('_pre.s3v$', f) and not re.search('_fx.s3v$', f) and not re.search('_pre_..\.s3v$', f)), None)
        if audio_file:
            jacket_file = None
            current_jacket_suffix = int(jacket_suffix)
            while not jacket_file and current_jacket_suffix >= 1:
                jacket_file_pattern = f"*{current_jacket_suffix}_b.png"
                jacket_file = next(iter(glob.glob(os.path.join(folderpath, jacket_file_pattern))), None)
                current_jacket_suffix -= 1
            
            return audio_file, jacket_file
        return None, None


    def create_video_file(audio_file, jacket_file, video_title):
        audio_file_path = os.path.join(folderpath, audio_file)
        audio = AudioSegment.from_file(audio_file_path)
        audio = audio.set_frame_rate(44100)
        audio.export('resampled_audio.wav', format='wav')
        audio = AudioFileClip('resampled_audio.wav')
        audio = audio.subclip(0, audio.duration - 0.1)


        if jacket_file:
            image = cv2.imread(jacket_file)
            image_resized = cv2.resize(image, (1080, 1080), interpolation=cv2.INTER_LANCZOS4)
            image_resized = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB)

            img = ImageClip(image_resized)
        else:
            print(f"No image found in folder: {folderpath}")
            exit(1)

        img = img.set_duration(audio.duration)
        img.fps = 15

        video = img.set_audio(audio)

        sanitized_video_title = get_sanitized_filename(video_title)
        output_file_name = os.path.join(output_directory or os.path.dirname(os.path.abspath(__file__)), sanitized_video_title + ".mov")
        video.write_videofile(output_file_name, audio_codec="pcm_s16le", codec="libx264", bitrate="5000k")
        
        audio.close()
        
        if os.path.exists('resampled_audio.wav'):
            os.remove('resampled_audio.wav')

    audio_created = False
    normal_audio_created = False
    for suffix, ending in special_cases.items():
        if suffix not in special_cases:
            continue
        
        audio_file, jacket_file = find_audio_and_jacket(suffix, suffix[1])
        #print(suffix)
        if audio_file and jacket_file:
            video_title = f"{artist_name} - {title_name} {ending}"
            create_video_file(audio_file, jacket_file, video_title)
            audio_created = True
            #break

    if not audio_created:
        if inf_ver > 1:
            audio_file_4i, jacket_file_4i = find_audio_and_jacket('_4i.s3v', '4')
            #print(f"audio_file_4i: {audio_file_4i}, jacket_file_4i: {jacket_file_4i}") 

            if audio_file_4i:
                if not jacket_file_4i:
                    for i in reversed(range(1, 4)):
                        jacket_file_4i = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', str(i))[1]
                        if jacket_file_4i:
                            break

                if jacket_file_4i:
                    ending = inf_cases.get(inf_ver, "")
                    video_title = f"{artist_name} - {title_name} {ending}"
                    create_video_file(audio_file_4i, jacket_file_4i, video_title)
                    audio_created = True
                else:
                    print("no jacket")
                    pass
            if not audio_created:
                audio_file_normal = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', '5')[0]
                #print("im here no 4i audio")
                if audio_file_normal:
                    jacket_file_below_4i = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', '5')[1]
                    #print(jacket_file_below_4i)
                    if not jacket_file_below_4i:
                        for i in reversed(range(1, 4)):
                            jacket_file_below_4i = find_audio_and_jacket(f'_{i}i.s3v', str(i))[1]
                            if jacket_file_below_4i:
                                break

                    if jacket_file_below_4i:
                        video_title = f"{artist_name} - {title_name}"
                        create_video_file(audio_file_normal, jacket_file_below_4i, video_title)
                        normal_audio_created = True
                        
            else:
                audio_file_normal = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', '5')[0]
                #print("im here already created inf video")
                if audio_file_normal:
                    jacket_file_below_4i = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', '3')[1]
                    #print(jacket_file_below_4i)
                    if not jacket_file_below_4i:
                        for i in reversed(range(1, 3)):
                            jacket_file_below_4i = find_audio_and_jacket(f'_{i}i.s3v', str(i))[1]
                            if jacket_file_below_4i:
                                break

                    if jacket_file_below_4i:
                        video_title = f"{artist_name} - {title_name}"
                        create_video_file(audio_file_normal, jacket_file_below_4i, video_title)
                        normal_audio_created = True
                
        else:
            audio_file_normal = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', '5')[0]
            #print("why am i here")
            if audio_file_normal:
                jacket_file_best = None
                for i in reversed(range(1, 6)):
                    if not jacket_file_best:
                        jacket_file_best = find_audio_and_jacket('.s3v', str(i))[1]
                    else:
                        break

                if jacket_file_best:
                    video_title = f"{artist_name} - {title_name}"
                    create_video_file(audio_file_normal, jacket_file_best, video_title)
                    normal_audio_created = True


    if not normal_audio_created:
        audio_file_normal = find_audio_and_jacket(r'^(?!.*_\d[a-zA-Z]\.s3v).*\.s3v$', '5')[0]
        #print("why tf am i here")
        #print(audio_file_normal)
        if audio_file_normal:
            jacket_file_best = None
            for i in reversed(range(1, 6)):
                if not jacket_file_best:
                    jacket_file_best = find_audio_and_jacket('.s3v', str(i))[1]
                else:
                    break

            if jacket_file_best:
                video_title = f"{artist_name} - {title_name}"
                create_video_file(audio_file_normal, jacket_file_best, video_title)
                normal_audio_created = True


for folderpath in args.folderpaths:
    create_video(folderpath, args.musicdb, args.outputdir)