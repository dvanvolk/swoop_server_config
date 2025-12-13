#!/usr/bin/env python3
"""
Movie Folder Cleanup Script
Handles duplicates, renames folders to Radarr format, and cleans up empty folders
"""

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
import json
import requests
import re
from typing import List, Dict, Any

# Configuration
# MOVIE_FOLDER = r"\\192.168.10.45\Movies"
MOVIE_FOLDER = r"\\192.168.10.45\Movies"

# TMDb API for looking up years (optional but recommended)
TMDB_API_KEY = "4e63389ad3c679bd8e3f087511d32e60"  # Get free key from https://www.themoviedb.org/settings/api
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"

DRY_RUN = True  # Set to False to actually make changes

def log(message):
    """Print with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def clean_movie_name(name):
    """Normalize movie name for comparison"""
    base_clean = name
    base_clean = re.sub(r'\s*\(\d{4}\)\s*', '', base_clean)   # Remove any existing year
    base_clean = base_clean.replace('_', ' ')                # Underscores → spaces
    base_clean = ' '.join(base_clean.split())                # Normalize whitespace
    name = radarr_title_case(base_clean)                     # Radarr title case
    return name

def extract_year(folder_name):
    """Extract year from folder name"""
    match = re.search(r'\((\d{4})\)', folder_name)
    return match.group(1) if match else None

def lookup_movie_year(title):
    """Look up movie year from TMDb API"""
    if not TMDB_API_KEY:
        return None
    
    try:
        params = {
            'api_key': TMDB_API_KEY,
            'query': title
        }
        response = requests.get(TMDB_SEARCH_URL, params=params, timeout=5)
        data = response.json()
        
        if data.get('results'):
            release_date = data['results'][0].get('release_date', '')
            if release_date:
                return release_date[:4]
    except Exception as e:
        log(f"TMDb lookup failed: {e}")
    
    return None

def handle_duplicates(dry_run=True):
    """Handle duplicate movie folders"""
    log("\n" + "="*80)
    log("HANDLING DUPLICATES")
    log("="*80)
    
    root = Path(MOVIE_FOLDER)
    movie_groups = {}
    
    # Scan and group duplicates
    for item in root.iterdir():
        if item.is_dir():
            clean_name = clean_movie_name(item.name)
            if clean_name not in movie_groups:
                movie_groups[clean_name] = []
            
            year = extract_year(item.name)
            video_files = list(item.glob('*.mkv')) + list(item.glob('*.mp4')) + \
                         list(item.glob('*.avi')) + list(item.glob('*.m4v'))
            size_mb = sum(f.stat().st_size for f in item.rglob('*') if f.is_file()) / (1024*1024)
            
            movie_groups[clean_name].append({
                'path': item,
                'name': item.name,
                'year': year,
                'size_mb': size_mb,
                'video_count': len(video_files)
            })
    
    # Process duplicates
    duplicates = {k: v for k, v in movie_groups.items() if len(v) > 1}
    
    actions = []
    for clean_name, folders in duplicates.items():
        # Sort by: has year, then size (keep largest)
        folders_sorted = sorted(folders, key=lambda x: (
            x['year'] is not None,  # Has year
            x['size_mb']             # Larger size
        ), reverse=True)
        
        keep = folders_sorted[0]
        remove = folders_sorted[1:]
        
        log(f"\nDuplicate: {clean_name}")
        log(f"  KEEP: {keep['name']} ({keep['size_mb']:.0f} MB)")
        
        for dup in remove:
            log(f"  DELETE: {dup['name']} ({dup['size_mb']:.0f} MB)")
            actions.append({
                'action': 'delete',
                'path': str(dup['path']),
                'reason': f"Duplicate of {keep['name']}"
            })
            
            if not dry_run:
                try:
                    shutil.rmtree(dup['path'])
                    log(f"    ✓ Deleted")
                except Exception as e:
                    log(f"    ✗ Error: {e}")
    
    log(f"\nDuplicates handled: {len(duplicates)} groups")
    return actions

def radarr_title_case(title: str) -> str:
    # Words Radarr keeps lowercase (unless first/last)
    small_words = {
        "a", "an", "the", "and", "but", "or", "nor",
        "as", "at", "by", "for", "in", "of", "on", "per",
        "to", "vs", "via", "from", "into", "onto"
    }

    # Special case: keep roman numerals uppercase
    roman_numeral = re.compile(r"^(?=[MDCLXVI])M{0,4}(CM|CD|D?C{0,3})"
                               r"(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$", re.I)

    words = title.split()
    result = []

    for i, word in enumerate(words):
        lower = word.lower()

        # Keep roman numerals uppercase
        if roman_numeral.match(word):
            result.append(word.upper())
            continue

        # Always capitalize first and last words
        if i == 0 or i == len(words) - 1:
            result.append(word.capitalize())
            continue

        # Lowercase small words
        if lower in small_words:
            result.append(lower)
            continue

        # Handle hyphenated words
        if "-" in word:
            parts = word.split("-")
            parts = [p.capitalize() if not roman_numeral.match(p) else p.upper()
                     for p in parts]
            result.append("-".join(parts))
            continue

        # Default: capitalize normally
        result.append(word.capitalize())

    return " ".join(result)

def rename_for_radarr(dry_run=True):
    """Rename folders to Radarr format."""
    log("\n" + "=" * 80)
    log("RENAMING FOLDERS TO RADARR FORMAT")
    log("=" * 80)

    root = Path(MOVIE_FOLDER)
    actions = []
    renamed_count = 0

    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue

        original_name = item.name

        # Skip folders already in correct format
        if re.match(r'^.+\s\(\d{4}\)$', original_name):
            continue

        # Clean base title BEFORE extracting year or TMDb search
        base_clean = clean_movie_name(original_name)
        # base_clean = re.sub(r'\s*\(\d{4}\)\s*', '', base_clean)   # Remove any existing year
        # base_clean = base_clean.replace('_', ' ')                # Underscores → spaces
        # base_clean = ' '.join(base_clean.split())                # Normalize whitespace
        # base_clean = radarr_title_case(base_clean)               # Radarr title case
        
        # First try: extract year directly
        year = extract_year(original_name)

        # Second try: TMDb lookup
        if not year:
            search_title = base_clean
            log(f"🔎 TMDb Lookup: '{search_title}'")

            year = lookup_movie_year(search_title)

        if not year:
            log(f"⚠️ No year found for: {original_name}")
            actions.append({
                "action": "skip",
                "path": str(item),
                "reason": "No year available"
            })
            continue

        # Build final Radarr-style folder name
        new_name = f"{base_clean} ({year})"
        new_path = item.parent / new_name

        # Check for collision
        if new_path.exists():
            log(f"⚠️ Target exists: {original_name} -> {new_name}")
            actions.append({
                "action": "skip",
                "path": str(item),
                "reason": f"Target {new_name} already exists"
            })
            continue

        # Report action
        log(f"Rename: {original_name}")
        log(f"    -> {new_name}")

        actions.append({
            "action": "rename",
            "old_path": str(item),
            "new_path": str(new_path),
            "old_name": original_name,
            "new_name": new_name
        })

        # Execute rename
        if not dry_run:
            try:
                item.rename(new_path)
                renamed_count += 1
                log("    ✓ Renamed")
            except Exception as e:
                log(f"    ✗ Error: {e}")

    log(f"\nFolders renamed: {renamed_count}")
    return actions

def cleanup_empty_folders(dry_run=True):
    """Remove empty movie folders"""
    log("\n" + "="*80)
    log("CLEANING UP EMPTY FOLDERS")
    log("="*80)
    
    root = Path(MOVIE_FOLDER)
    actions = []
    
    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        
        # Check for video files
        video_files = list(item.glob('*.mkv')) + list(item.glob('*.mp4')) + \
                     list(item.glob('*.avi')) + list(item.glob('*.m4v'))
        
        if len(video_files) == 0:
            log(f"Empty: {item.name}")
            # Emit a standard 'delete' action with 'source' set to the folder.
            # The executor will only remove the folder if it is empty.
            actions.append({
                'action': 'delete',
                'source': str(item)
            })

            if not dry_run:
                try:
                    # Only remove the directory if it is empty.
                    Path(item).rmdir()
                    log(f"  ✓ Deleted (empty)")
                except Exception as e:
                    log(f"  ✗ Error removing folder (may not be empty): {e}")
    
    log(f"\nEmpty folders cleaned: {len(actions)}")
    return actions


def execute_actions_file(actions_file: str = 'actions.json', dry_run: bool = True) -> List[Dict[str, Any]]:
    """Execute actions described in a JSON file.

        Supported actions:
            - move: requires 'source' and 'destination'
            - delete: requires 'source' (will remove files, or remove directory only if empty)
            - rename: requires 'old_path' and 'new_path'
            - keep / skip: recorded but not operated on
    Returns list of action results (dicts).
    """
    results = []
    folders_to_check = set()

    if not os.path.exists(actions_file):
        log(f"Actions file not found: {actions_file}")
        return results

    with open(actions_file, 'r', encoding='utf-8') as f:
        try:
            actions = json.load(f)
        except Exception as e:
            log(f"Failed to read actions file: {e}")
            return results

    for idx, action in enumerate(actions, 1):
        a_type = action.get('action')
        log(f"\n[{idx}/{len(actions)}] Action: {a_type}")

        try:
            if a_type == 'move':
                pass
                # src = action.get('path')
                # dest = action.get('destination')
                # if not src or not dest:
                #     raise ValueError('move action requires source and destination')

                # filename = Path(src).name
                # dest_path = Path(dest)
                # full_dest = dest_path / filename

                # log(f"Move: {src}")
                # log(f"    -> {full_dest}")

                # if not dry_run:
                #     dest_path.mkdir(parents=True, exist_ok=True)
                #     shutil.move(src, str(full_dest))

                # folders_to_check.add(str(Path(src).parent))
                # results.append({'action': 'move', 'source': src, 'destination': str(full_dest), 'status': 'ok'})

            elif a_type == 'delete':
                src = action.get('source') or action.get('path')
                if not src:
                    raise ValueError('delete action requires source')

                src_path = Path(src)
                log(f"Delete: {src}")

                if not dry_run:
                    if src_path.exists():
                        if src_path.is_file():
                            # Remove file
                            src_path.unlink()
                            log(f"    ✓ File removed")
                        elif src_path.is_dir():
                            # Remove files directly inside the directory (non-recursive),
                            # then attempt to remove the directory if it's empty.
                            removed = []
                            for child in sorted(src_path.iterdir()):
                                if child.is_file():
                                    log(f"    Removing file: {child.name}")
                                    child.unlink()
                                    removed.append(str(child))

                            try:
                                src_path.rmdir()
                                log(f"    ✓ Empty directory removed")
                            except Exception as e:
                                log(f"    ✗ Directory not removed (not empty?): {e}")
                        else:
                            log(f"    ✗ Unknown path type: {src}")
                    else:
                        log(f"    ✗ Path does not exist: {src}")

                # Track parent for potential cleanup
                try:
                    folders_to_check.add(str(src_path.parent))
                except Exception:
                    pass

                results.append({'action': 'delete', 'source': src, 'status': 'ok'})

            elif a_type == 'rename':
                pass
                # old = action.get('old_path') or action.get('source')
                # new = action.get('new_path') or action.get('destination')
                # if not old or not new:
                #     raise ValueError('rename action requires old_path and new_path')

                # log(f"Rename: {old}")
                # log(f"    -> {new}")
                # if not dry_run:
                #     Path(old).rename(new)

                # folders_to_check.add(str(Path(old).parent))
                # results.append({'action': 'rename', 'old': old, 'new': new, 'status': 'ok'})

            # 'delete_empty' action removed - empty-folder deletes are now standard 'delete' actions

            elif a_type in ('keep', 'skip'):
                results.append({'action': a_type, 'status': 'skipped'})

            else:
                log(f"Unknown action type: {a_type}")
                results.append({'action': a_type, 'status': 'unknown'})

        except Exception as e:
            log(f"  ✗ Error executing action: {e}")
            results.append({'action': a_type, 'status': 'error', 'error': str(e)})

    # Attempt to remove any empty source folders
    for folder in sorted(folders_to_check):
        try:
            p = Path(folder)
            if p.exists() and p.is_dir() and not any(p.iterdir()):
                log(f"Removing empty folder: {folder}")
                if not dry_run:
                    p.rmdir()
        except Exception as e:
            log(f"Failed to remove folder {folder}: {e}")

    return results

def main():
    """Main cleanup workflow or action executor"""
    # Parse command-line arguments
    actions_file = None
    execute_mode = False
    dry_run = DRY_RUN
    
    if len(sys.argv) > 1:
        # Check for actions file argument
        if sys.argv[1].endswith('.json'):
            actions_file = sys.argv[1]
            execute_mode = True
        
        # Check for --live flag (overrides DRY_RUN)
        if '--live' in sys.argv or '--no-dry-run' in sys.argv:
            dry_run = False
        
        # Check for --dry-run flag
        if '--dry-run' in sys.argv:
            dry_run = True
    
    if execute_mode and actions_file:
        # Mode: Execute pre-generated actions from JSON file
        log("="*80)
        log("EXECUTING ACTIONS FROM FILE")
        log("="*80)
        log(f"Actions file: {actions_file}")
        log(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (making changes!)'}")
        
        if not dry_run:
            response = input("\n⚠️  LIVE MODE - Files will be moved/deleted! Continue? (yes/no): ")
            if response.lower() != 'yes':
                log("Cancelled")
                return
        
        results = execute_actions_file(actions_file, dry_run=dry_run)
        
        log("\n" + "="*80)
        log("EXECUTION SUMMARY")
        log("="*80)
        log(f"Total actions processed: {len(results)}")
        
        if dry_run:
            log("\n⚠️  This was a DRY RUN - no changes were made")
            log("Run with --live flag to apply changes:")
            log(f"  python movie_cleanup.py {actions_file} --live")
    else:
        # Mode: Generate new actions from analysis
        log("="*80)
        log("MOVIE FOLDER CLEANUP")
        log("="*80)
        log(f"Target: {MOVIE_FOLDER}")
        log(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (making changes!)'}")
        
        if not dry_run:
            response = input("\n⚠️  LIVE MODE - Files will be deleted/renamed! Continue? (yes/no): ")
            if response.lower() != 'yes':
                log("Cancelled")
                return
        
        all_actions = []
        
        # Step 1: Handle duplicates
        duplicate_actions = handle_duplicates(dry_run)
        all_actions.extend(duplicate_actions)
        
        # Step 2: Clean empty folders
        # empty_actions = cleanup_empty_folders(dry_run)
        # all_actions.extend(empty_actions)
        
        # Step 3: Rename for Radarr (do this after cleanup to avoid conflicts)
        rename_actions = rename_for_radarr(dry_run)
        all_actions.extend(rename_actions)
        
        # Save action log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"cleanup_actions_{timestamp}.json"
        with open(log_file, 'w') as f:
            json.dump(all_actions, f, indent=2)
        
        log("\n" + "="*80)
        log("SUMMARY")
        log("="*80)
        log(f"Total actions: {len(all_actions)}")
        log(f"Action log saved: {log_file}")
        
        if dry_run:
            log("\n⚠️  This was a DRY RUN - no changes were made")
            log("To execute actions:")
            log(f"  python movie_cleanup.py {log_file} --live")

if __name__ == "__main__":
    main()