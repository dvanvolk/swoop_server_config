#!/usr/bin/env python3
"""
Media File Organizer
This script copies MKV files from Downloads to appropriate folders (Movies/TVShows/Music)
based on filename patterns, organizing them into proper subdirectories
"""

import os
import shutil
import re
from pathlib import Path

# Configuration - Update these paths as needed
DOWNLOADS_PATH = r"\\192.168.10.45\Downloads"
MOVIES_PATH = r"\\192.168.10.45\Movies"
TVSHOWS_PATH = r"\\192.168.10.45\TVShows"
MUSIC_PATH = r"\\192.168.10.45\Music"

# Input file containing the list of files
INPUT_FILE = "downloads.txt"

# DRY RUN MODE - Set to False to actually copy files
DRY_RUN = False  # When True, only shows what would be done without copying

# QUALITY COMPARISON - Set to True to replace lower quality files with higher quality ones
REPLACE_WITH_BETTER_QUALITY = True  # When True, will replace existing files if new file is better quality

# Color codes for terminal output
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

def extract_tv_show_info(filename):
    """Extract TV show name and season from filename"""
    # Try to match S##E## pattern
    match = re.search(r'(.+?)[.\s]+S(\d{1,2})E\d{1,2}', filename, re.IGNORECASE)
    if match:
        show_name = match.group(1).replace('.', ' ').strip()
        season_num = int(match.group(2))
        return show_name, season_num
    
    # Try to match ##x## pattern
    match = re.search(r'(.+?)[.\s]+(\d{1,2})x\d{1,2}', filename, re.IGNORECASE)
    if match:
        show_name = match.group(1).replace('.', ' ').strip()
        season_num = int(match.group(2))
        return show_name, season_num
    
    return None, None

def extract_movie_info(filename):
    """Extract movie name and year from filename"""
    # Try to match pattern with year (e.g., "Movie Name 2019" or "Movie.Name.2019")
    match = re.search(r'(.+?)[.\s]+((?:19|20)\d{2})', filename, re.IGNORECASE)
    if match:
        movie_name = match.group(1).replace('.', ' ').strip()
        year = match.group(2)
        return f"{movie_name} ({year})"
    
    # If no year found, just clean up the filename
    movie_name = re.sub(r'\.(mkv|mp4|avi)$', '', filename, flags=re.IGNORECASE)
    movie_name = re.sub(r'[\.\-_]+', ' ', movie_name)
    # Remove common tags
    movie_name = re.sub(r'\b(1080p|720p|2160p|BluRay|WEB-DL|x265|x264|RARBG|HEVC|H\.264|H\.265)\b.*$', '', movie_name, flags=re.IGNORECASE)
    return movie_name.strip()

def is_tv_show(filename):
    """Determine if filename indicates a TV show"""
    if re.search(r'S\d{1,2}E\d{1,2}', filename, re.IGNORECASE):
        return True
    if re.search(r'\d{1,2}x\d{1,2}', filename, re.IGNORECASE):
        return True
    return False

def is_music(filename):
    """Determine if filename indicates music"""
    music_patterns = ['album', 'soundtrack', 'ost', 'music']
    return any(pattern in filename.lower() for pattern in music_patterns)

def check_file_exists_in_tree(root_folder, filename):
    """Check if a file exists anywhere in the folder tree"""
    for dirpath, dirnames, filenames in os.walk(root_folder):
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return None

def extract_quality_info(filename):
    """Extract quality information from filename"""
    quality_score = 0
    info = {
        'resolution': 0,
        'codec': '',
        'is_hdr': False,
        'audio': ''
    }
    
    # Resolution scoring (higher is better)
    if re.search(r'\b2160p\b', filename, re.IGNORECASE):
        info['resolution'] = 2160
        quality_score += 4000
    elif re.search(r'\b1080p\b', filename, re.IGNORECASE):
        info['resolution'] = 1080
        quality_score += 2000
    elif re.search(r'\b720p\b', filename, re.IGNORECASE):
        info['resolution'] = 720
        quality_score += 1000
    elif re.search(r'\b480p\b', filename, re.IGNORECASE):
        info['resolution'] = 480
        quality_score += 500
    
    # Codec scoring (modern codecs are better)
    if re.search(r'\b(x265|HEVC|H\.?265|AV1)\b', filename, re.IGNORECASE):
        info['codec'] = 'x265/HEVC/AV1'
        quality_score += 300
    elif re.search(r'\b(x264|H\.?264|AVC)\b', filename, re.IGNORECASE):
        info['codec'] = 'x264/H.264'
        quality_score += 200
    
    # HDR content
    if re.search(r'\b(HDR|HDR10|DoVi|Dolby[\s\.]?Vision)\b', filename, re.IGNORECASE):
        info['is_hdr'] = True
        quality_score += 500
    
    # Source quality (BluRay > WEB-DL > HDTV)
    if re.search(r'\bBluRay\b', filename, re.IGNORECASE):
        quality_score += 400
    elif re.search(r'\b(WEB-DL|WEBDL|WEBRip)\b', filename, re.IGNORECASE):
        quality_score += 300
    elif re.search(r'\bHDTV\b', filename, re.IGNORECASE):
        quality_score += 200
    
    # Audio quality
    if re.search(r'\b(Atmos|TrueHD|DTS-HD|DTS-X)\b', filename, re.IGNORECASE):
        info['audio'] = 'High-quality audio'
        quality_score += 100
    elif re.search(r'\b(DDP|DD[\+\.]?5\.1|AC3)\b', filename, re.IGNORECASE):
        info['audio'] = 'Standard audio'
        quality_score += 50
    
    return quality_score, info

def compare_quality(new_file, existing_file):
    """Compare quality of two files. Returns True if new_file is better."""
    new_score, new_info = extract_quality_info(new_file)
    existing_score, existing_info = extract_quality_info(existing_file)
    
    # Also consider file size as a tiebreaker (larger is usually better for same resolution)
    try:
        new_size = os.path.getsize(new_file)
        existing_size = os.path.getsize(existing_file)
        
        # If scores are equal, prefer larger file (up to a point - add 10% size bonus)
        if new_score == existing_score:
            if new_size > existing_size * 1.1:  # New file is at least 10% larger
                new_score += 50
    except:
        pass
    
    return new_score > existing_score, new_score, existing_score, new_info, existing_info

def copy_tv_show(source_path, filename, base_folder, dry_run=False, replace_better=False):
    """Copy TV show file to appropriate show/season folder"""
    show_name, season_num = extract_tv_show_info(filename)
    
    if not show_name or season_num is None:
        print(f"{Colors.RED}  Could not extract show info from filename{Colors.RESET}")
        return "error"
    
    # Check if file already exists anywhere in TV Shows folder
    existing_path = check_file_exists_in_tree(base_folder, filename)
    if existing_path:
        if replace_better:
            is_better, new_score, old_score, new_info, old_info = compare_quality(source_path, existing_path)
            if is_better:
                print(f"{Colors.CYAN}  Found better quality version!{Colors.RESET}")
                print(f"    New: {new_info['resolution']}p {new_info['codec']} (score: {new_score})")
                print(f"    Old: {old_info['resolution']}p {old_info['codec']} (score: {old_score})")
                if dry_run:
                    print(f"{Colors.YELLOW}  [DRY RUN] Would replace: {existing_path}{Colors.RESET}")
                    return "would_replace"
                else:
                    try:
                        os.remove(existing_path)
                        shutil.copy2(source_path, existing_path)
                        print(f"{Colors.GREEN}  REPLACED with better quality: {existing_path}{Colors.RESET}")
                        return "replaced"
                    except Exception as e:
                        print(f"{Colors.RED}  ERROR replacing: {e}{Colors.RESET}")
                        return "error"
            else:
                print(f"{Colors.YELLOW}  SKIPPED (existing file is same/better quality): {existing_path}{Colors.RESET}")
                print(f"    New: {new_info['resolution']}p {new_info['codec']} (score: {new_score})")
                print(f"    Old: {old_info['resolution']}p {old_info['codec']} (score: {old_score})")
                return "skipped"
        else:
            print(f"{Colors.YELLOW}  SKIPPED (already exists): {existing_path}{Colors.RESET}")
            return "skipped"
    
    # Create destination path: TVShows/Show Name/Season #/filename
    dest_folder = os.path.join(base_folder, show_name, f"Season {season_num}")
    dest_path = os.path.join(dest_folder, filename)
    
    if dry_run:
        print(f"{Colors.CYAN}  [DRY RUN] Would copy to: {dest_folder}{Colors.RESET}")
        return "would_copy"
    
    try:
        os.makedirs(dest_folder, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        print(f"{Colors.GREEN}  COPIED to: {dest_folder}{Colors.RESET}")
        return "copied"
    except Exception as e:
        print(f"{Colors.RED}  ERROR: {e}{Colors.RESET}")
        return "error"

def copy_movie(source_path, filename, base_folder, dry_run=False, replace_better=False):
    """Copy movie file to appropriate movie folder"""
    # Check if file already exists anywhere in Movies folder
    existing_path = check_file_exists_in_tree(base_folder, filename)
    if existing_path:
        if replace_better:
            is_better, new_score, old_score, new_info, old_info = compare_quality(source_path, existing_path)
            if is_better:
                print(f"{Colors.CYAN}  Found better quality version!{Colors.RESET}")
                print(f"    New: {new_info['resolution']}p {new_info['codec']} (score: {new_score})")
                print(f"    Old: {old_info['resolution']}p {old_info['codec']} (score: {old_score})")
                if dry_run:
                    print(f"{Colors.YELLOW}  [DRY RUN] Would replace: {existing_path}{Colors.RESET}")
                    return "would_replace"
                else:
                    try:
                        os.remove(existing_path)
                        shutil.copy2(source_path, existing_path)
                        print(f"{Colors.GREEN}  REPLACED with better quality: {existing_path}{Colors.RESET}")
                        return "replaced"
                    except Exception as e:
                        print(f"{Colors.RED}  ERROR replacing: {e}{Colors.RESET}")
                        return "error"
            else:
                print(f"{Colors.YELLOW}  SKIPPED (existing file is same/better quality): {existing_path}{Colors.RESET}")
                print(f"    New: {new_info['resolution']}p {new_info['codec']} (score: {new_score})")
                print(f"    Old: {old_info['resolution']}p {old_info['codec']} (score: {old_score})")
                return "skipped"
        else:
            print(f"{Colors.YELLOW}  SKIPPED (already exists): {existing_path}{Colors.RESET}")
            return "skipped"
    
    # Extract movie name for folder
    folder_name = extract_movie_info(filename)
    
    # Create destination path: Movies/Movie Name (Year)/filename
    dest_folder = os.path.join(base_folder, folder_name)
    dest_path = os.path.join(dest_folder, filename)
    
    if dry_run:
        print(f"{Colors.CYAN}  [DRY RUN] Would copy to: {dest_folder}{Colors.RESET}")
        return "would_copy"
    
    try:
        os.makedirs(dest_folder, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        print(f"{Colors.GREEN}  COPIED to: {dest_folder}{Colors.RESET}")
        return "copied"
    except Exception as e:
        print(f"{Colors.RED}  ERROR: {e}{Colors.RESET}")
        return "error"

def copy_music(source_path, filename, base_folder, dry_run=False, replace_better=False):
    """Copy music file to music folder"""
    # Check if file already exists anywhere in Music folder
    existing_path = check_file_exists_in_tree(base_folder, filename)
    if existing_path:
        if replace_better:
            is_better, new_score, old_score, new_info, old_info = compare_quality(source_path, existing_path)
            if is_better:
                print(f"{Colors.CYAN}  Found better quality version!{Colors.RESET}")
                print(f"    New: {new_info['resolution']}p {new_info['codec']} (score: {new_score})")
                print(f"    Old: {old_info['resolution']}p {old_info['codec']} (score: {old_score})")
                if dry_run:
                    print(f"{Colors.YELLOW}  [DRY RUN] Would replace: {existing_path}{Colors.RESET}")
                    return "would_replace"
                else:
                    try:
                        os.remove(existing_path)
                        shutil.copy2(source_path, existing_path)
                        print(f"{Colors.GREEN}  REPLACED with better quality: {existing_path}{Colors.RESET}")
                        return "replaced"
                    except Exception as e:
                        print(f"{Colors.RED}  ERROR replacing: {e}{Colors.RESET}")
                        return "error"
            else:
                print(f"{Colors.YELLOW}  SKIPPED (existing file is same/better quality): {existing_path}{Colors.RESET}")
                print(f"    New: {new_info['resolution']}p {new_info['codec']} (score: {new_score})")
                print(f"    Old: {old_info['resolution']}p {old_info['codec']} (score: {old_score})")
                return "skipped"
        else:
            print(f"{Colors.YELLOW}  SKIPPED (already exists): {existing_path}{Colors.RESET}")
            return "skipped"
    
    dest_path = os.path.join(base_folder, filename)
    
    if dry_run:
        print(f"{Colors.CYAN}  [DRY RUN] Would copy to: {base_folder}{Colors.RESET}")
        return "would_copy"
    
    try:
        os.makedirs(base_folder, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        print(f"{Colors.GREEN}  COPIED to: {base_folder}{Colors.RESET}")
        return "copied"
    except Exception as e:
        print(f"{Colors.RED}  ERROR: {e}{Colors.RESET}")
        return "error"

def main():
    """Main processing function"""
    print(f"{Colors.CYAN}Starting Media File Organizer...{Colors.RESET}")
    if DRY_RUN:
        print(f"{Colors.YELLOW}*** DRY RUN MODE - No files will be copied ***{Colors.RESET}")
    print(f"{Colors.CYAN}================================{Colors.RESET}")
    
    # Check if input file exists
    if not os.path.exists(INPUT_FILE):
        print(f"{Colors.RED}ERROR: Input file '{INPUT_FILE}' not found!{Colors.RESET}")
        print(f"{Colors.RED}Please create a text file with the list of files to process.{Colors.RESET}")
        return
    
    # Read the file list
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        files = [line.strip() for line in f if line.strip().endswith('.mkv')]
    
    # Statistics
    stats = {
        'total': 0,
        'movies': 0,
        'tvshows': 0,
        'music': 0,
        'copied': 0,
        'replaced': 0,
        'would_copy': 0,
        'would_replace': 0,
        'skipped': 0,
        'errors': 0
    }
    
    for file_path in files:
        if not file_path:
            continue
        
        # Extract filename from path
        filename = os.path.basename(file_path)
        
        print(f"\n{Colors.WHITE}Processing: {filename}{Colors.RESET}")
        
        stats['total'] += 1
        
        # Determine destination and copy
        result = None
        if is_tv_show(filename):
            print(f"  {Colors.CYAN}Category: TV Show{Colors.RESET}")
            stats['tvshows'] += 1
            result = copy_tv_show(file_path, filename, TVSHOWS_PATH, dry_run=DRY_RUN, replace_better=REPLACE_WITH_BETTER_QUALITY)
        elif is_music(filename):
            print(f"  {Colors.CYAN}Category: Music{Colors.RESET}")
            stats['music'] += 1
            result = copy_music(file_path, filename, MUSIC_PATH, dry_run=DRY_RUN, replace_better=REPLACE_WITH_BETTER_QUALITY)
        else:
            print(f"  {Colors.CYAN}Category: Movie{Colors.RESET}")
            stats['movies'] += 1
            result = copy_movie(file_path, filename, MOVIES_PATH, dry_run=DRY_RUN, replace_better=REPLACE_WITH_BETTER_QUALITY)
        
        if result == "copied":
            stats['copied'] += 1
        elif result == "replaced":
            stats['replaced'] += 1
        elif result == "would_copy":
            stats['would_copy'] += 1
        elif result == "would_replace":
            stats['would_replace'] += 1
        elif result == "skipped":
            stats['skipped'] += 1
        elif result == "error":
            stats['errors'] += 1
    
    # Display summary
    print(f"\n{Colors.CYAN}================================{Colors.RESET}")
    print(f"{Colors.CYAN}Summary:{Colors.RESET}")
    print(f"{Colors.WHITE}  Total MKV files processed: {stats['total']}{Colors.RESET}")
    print(f"{Colors.WHITE}  Movies: {stats['movies']}{Colors.RESET}")
    print(f"{Colors.WHITE}  TV Shows: {stats['tvshows']}{Colors.RESET}")
    print(f"{Colors.WHITE}  Music: {stats['music']}{Colors.RESET}")
    if DRY_RUN:
        print(f"{Colors.CYAN}  Would copy: {stats['would_copy']}{Colors.RESET}")
        print(f"{Colors.CYAN}  Would replace (better quality): {stats['would_replace']}{Colors.RESET}")
    else:
        print(f"{Colors.GREEN}  Successfully copied: {stats['copied']}{Colors.RESET}")
        print(f"{Colors.GREEN}  Replaced (better quality): {stats['replaced']}{Colors.RESET}")
    print(f"{Colors.YELLOW}  Skipped (already exist): {stats['skipped']}{Colors.RESET}")
    print(f"{Colors.RED}  Errors: {stats['errors']}{Colors.RESET}")
    print(f"{Colors.CYAN}================================{Colors.RESET}")
    if DRY_RUN:
        print(f"{Colors.YELLOW}Set DRY_RUN = False to actually copy files{Colors.RESET}")
    if REPLACE_WITH_BETTER_QUALITY:
        print(f"{Colors.CYAN}Quality comparison is ENABLED{Colors.RESET}")

if __name__ == "__main__":
    main()