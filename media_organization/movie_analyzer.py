#!/usr/bin/env python3
"""
Movie Folder Analyzer for Radarr
Scans movie folders, identifies duplicates, checks Radarr compatibility,
and compares with Radarr's database to find import issues
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import requests

class OutputLogger:
    """Dual output to console and file"""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'w', encoding='utf-8')
    
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    
    def flush(self):
        self.terminal.flush()
        self.log.flush()
    
    def close(self):
        self.log.close()

def clean_movie_name(name):
    """Normalize movie name for comparison"""
    # Remove year in parentheses
    name = re.sub(r'\s*\(\d{4}\)\s*', '', name)
    # Convert to lowercase
    name = name.lower()
    # Remove special characters and extra spaces
    name = re.sub(r'[^\w\s]', '', name)
    # Remove extra whitespace
    name = ' '.join(name.split())
    return name

def extract_year(folder_name):
    """Extract year from folder name if present"""
    match = re.search(r'\((\d{4})\)', folder_name)
    return match.group(1) if match else None

def is_radarr_format(folder_name):
    """Check if folder follows Radarr naming convention: 'Movie Title (Year)'"""
    pattern = r'^.+\s\(\d{4}\)$'
    return bool(re.match(pattern, folder_name))

def get_radarr_movies(api_url, api_key):
    """Fetch movies from Radarr API"""
    try:
        headers = {'X-Api-Key': api_key}
        response = requests.get(f"{api_url}/api/v3/movie", headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Radarr: {e}")
        return None

def scan_movie_folder(root_path):
    """Scan the movie folder and return organized data"""
    root = Path(root_path)
    
    if not root.exists():
        return None, f"Error: Path '{root_path}' does not exist"
    
    movies = []
    movie_groups = defaultdict(list)
    
    # Scan immediate subdirectories (movie folders)
    for item in sorted(root.iterdir()):
        if item.is_dir():
            folder_name = item.name
            clean_name = clean_movie_name(folder_name)
            year = extract_year(folder_name)
            radarr_compatible = is_radarr_format(folder_name)
            
            # Get movie files in folder
            video_extensions = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv'}
            video_files = [f.name for f in item.iterdir() 
                          if f.is_file() and f.suffix.lower() in video_extensions]
            
            folder_size_mb = sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / (1024*1024)
            
            movie_info = {
                'original_name': folder_name,
                'clean_name': clean_name,
                'year': year,
                'radarr_compatible': radarr_compatible,
                'path': str(item),
                'video_files': video_files,
                'video_count': len(video_files),
                'size_mb': round(folder_size_mb, 2)
            }
            
            movies.append(movie_info)
            movie_groups[clean_name].append(movie_info)
    
    return movies, movie_groups

def compare_with_radarr(movies, radarr_movies):
    """Compare local movies with Radarr's database"""
    if not radarr_movies:
        return None
    
    # Build Radarr movie lookup
    radarr_folders = {Path(m['path']).name.lower(): m for m in radarr_movies}
    radarr_titles = {clean_movie_name(m['title']): m for m in radarr_movies}
    
    in_radarr = []
    not_in_radarr = []
    
    for movie in movies:
        folder_lower = movie['original_name'].lower()
        
        # Check if folder exists in Radarr
        if folder_lower in radarr_folders:
            radarr_movie = radarr_folders[folder_lower]
            movie['in_radarr'] = True
            movie['radarr_status'] = radarr_movie.get('status', 'unknown')
            movie['radarr_monitored'] = radarr_movie.get('monitored', False)
            in_radarr.append(movie)
        # Check by clean title
        elif movie['clean_name'] in radarr_titles:
            movie['in_radarr'] = True
            movie['radarr_status'] = 'matched_by_title'
            in_radarr.append(movie)
        else:
            movie['in_radarr'] = False
            not_in_radarr.append(movie)
    
    return {
        'in_radarr': in_radarr,
        'not_in_radarr': not_in_radarr,
        'total_radarr': len(radarr_movies)
    }

def generate_report(root_path, radarr_api_url=None, radarr_api_key=None):
    """Generate a comprehensive report"""
    # Setup output logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"movie_analysis_report_{timestamp}.txt"
    logger = OutputLogger(report_file)
    sys.stdout = logger
    
    print("=" * 80)
    print("MOVIE FOLDER ANALYSIS REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scanning: {root_path}\n")
    
    movies, movie_groups = scan_movie_folder(root_path)
    
    if movies is None:
        print(movie_groups)  # Error message
        logger.close()
        sys.stdout = logger.terminal
        return
    
    total_movies = len(movies)
    radarr_compatible = sum(1 for m in movies if m['radarr_compatible'])
    needs_rename = total_movies - radarr_compatible
    
    print(f"Total movie folders found: {total_movies}")
    print(f"Radarr-compatible format: {radarr_compatible}")
    print(f"Needs renaming: {needs_rename}")
    
    # Radarr comparison
    radarr_comparison = None
    if radarr_api_url and radarr_api_key:
        print(f"\nConnecting to Radarr at {radarr_api_url}...")
        radarr_movies = get_radarr_movies(radarr_api_url, radarr_api_key)
        if radarr_movies:
            print(f"Radarr has {len(radarr_movies)} movies in database")
            radarr_comparison = compare_with_radarr(movies, radarr_movies)
            print(f"Movies in Radarr: {len(radarr_comparison['in_radarr'])}")
            print(f"Movies NOT in Radarr: {len(radarr_comparison['not_in_radarr'])}")
    
    # Find duplicates
    duplicates = {name: folders for name, folders in movie_groups.items() if len(folders) > 1}
    
    if duplicates:
        print(f"\n{'=' * 80}")
        print(f"DUPLICATE MOVIES FOUND: {len(duplicates)}")
        print("=" * 80)
        
        for clean_name, folders in sorted(duplicates.items()):
            print(f"\n🎬 Duplicate: '{clean_name}'")
            print("   Folders:")
            for i, folder in enumerate(folders, 1):
                year_info = f" ({folder['year']})" if folder['year'] else " (no year)"
                files_info = f" - {folder['video_count']} video file(s), {folder['size_mb']} MB"
                radarr_info = ""
                if radarr_comparison:
                    radarr_info = " [IN RADARR]" if folder.get('in_radarr') else " [NOT IN RADARR]"
                print(f"   {i}. {folder['original_name']}{year_info}{files_info}{radarr_info}")
                print(f"      Path: {folder['path']}")
    else:
        print("\n✓ No duplicates found!")
    
    # Movies NOT in Radarr (cannot be imported)
    if radarr_comparison and radarr_comparison['not_in_radarr']:
        not_in_radarr = radarr_comparison['not_in_radarr']
        print(f"\n{'=' * 80}")
        print(f"⚠️  MOVIES NOT IN RADARR (CANNOT IMPORT): {len(not_in_radarr)}")
        print("=" * 80)
        print("\nThese folders exist on disk but are not recognized by Radarr.")
        print("Common reasons: naming issues, missing year, special characters\n")
        
        for movie in sorted(not_in_radarr, key=lambda x: x['original_name']):
            year_status = f"({movie['year']})" if movie['year'] else "⚠️  NO YEAR"
            radarr_fmt = "✓" if movie['radarr_compatible'] else "✗"
            print(f"• {movie['original_name']} {year_status}")
            print(f"  Radarr format: {radarr_fmt} | Videos: {movie['video_count']} | Size: {movie['size_mb']} MB")
            print(f"  Clean name: {movie['clean_name']}")
            print(f"  Path: {movie['path']}")
            print()
    
    # Movies needing rename
    if needs_rename > 0:
        print(f"\n{'=' * 80}")
        print(f"FOLDERS NEEDING RADARR FORMAT: {needs_rename}")
        print("=" * 80)
        print("\nRadarr expects: 'Movie Title (Year)'\n")
        
        count = 0
        for movie in sorted(movies, key=lambda x: x['original_name']):
            if not movie['radarr_compatible']:
                count += 1
                if count > 50:  # Limit output for readability
                    print(f"... and {needs_rename - 50} more folders")
                    break
                    
                year_status = f"Has year ({movie['year']})" if movie['year'] else "⚠️  Missing year"
                radarr_info = ""
                if radarr_comparison:
                    radarr_info = " [IN RADARR]" if movie.get('in_radarr') else " [NOT IN RADARR]"
                print(f"• {movie['original_name']}{radarr_info}")
                print(f"  Status: {year_status}")
                print(f"  Clean name: {movie['clean_name']}")
                if movie['video_files']:
                    print(f"  Files: {', '.join(movie['video_files'][:2])}")
                print()
    
    # Movies without video files
    no_videos = [m for m in movies if m['video_count'] == 0]
    if no_videos:
        print(f"\n{'=' * 80}")
        print(f"⚠️  FOLDERS WITHOUT VIDEO FILES: {len(no_videos)}")
        print("=" * 80)
        for movie in no_videos:
            radarr_info = ""
            if radarr_comparison:
                radarr_info = " [IN RADARR]" if movie.get('in_radarr') else " [NOT IN RADARR]"
            print(f"• {movie['original_name']}{radarr_info}")
            print(f"  Path: {movie['path']}\n")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total folders: {total_movies}")
    print(f"Duplicates: {len(duplicates)}")
    print(f"Radarr-compatible format: {radarr_compatible}")
    print(f"Need renaming: {needs_rename}")
    print(f"Empty folders: {len(no_videos)}")
    if radarr_comparison:
        print(f"\nRadarr Integration:")
        print(f"  In Radarr database: {len(radarr_comparison['in_radarr'])}")
        print(f"  NOT in Radarr (cannot import): {len(radarr_comparison['not_in_radarr'])}")
        print(f"  Total in Radarr DB: {radarr_comparison['total_radarr']}")
    print("=" * 80)
    print(f"\nReport saved to: {report_file}")
    
    # Close logger and restore stdout
    logger.close()
    sys.stdout = logger.terminal
    print(f"\n✓ Report saved to: {report_file}")

if __name__ == "__main__":
    # Your NAS movie folder path
    movie_folder_path = r"\\192.168.10.45\Movies"
    
    # Radarr API settings (optional - leave as None to skip Radarr comparison)
    # Get your API key from Radarr: Settings > General > Security > API Key
    radarr_url = "http://192.168.10.25:7878"  # Change to your Radarr URL
    radarr_api_key = "c5387e1f53c1418cb0003c311caa8ca8"  # Set to your API key like "1234567890abcdef1234567890abcdef"
    
    print(f"Analyzing movies at: {movie_folder_path}")
    if radarr_api_key:
        print(f"Will compare with Radarr at: {radarr_url}")
    else:
        print("Radarr comparison disabled (set radarr_api_key to enable)")
    print("This may take a moment depending on the number of movies...\n")
    
    generate_report(movie_folder_path, radarr_url, radarr_api_key)