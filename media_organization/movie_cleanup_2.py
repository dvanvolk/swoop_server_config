#!/usr/bin/env python3
"""
Movie Folder Cleanup Script - Two Phase Operation
Phase 1: Review files and generate actions.json
Phase 2: Execute actions from actions.json
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict
import re


class ActionGenerator:
    """Phase 1: Generate actions file from diff review"""
    
    def __init__(self, diff_file_path: str):
        self.diff_file_path = diff_file_path
        self.actions = []
        
    def parse_diff_file(self) -> List[str]:
        """Parse the diff file and extract file paths"""
        files = []
        
        with open(self.diff_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Look for lines that contain network paths
                if line and '\\\\192.168.10.45\\Movies\\' in line:
                    # Extract just the path portion
                    match = re.search(r'(\\\\192\.168\.10\.45\\Movies\\.*\.mkv)', line)
                    if match:
                        files.append(match.group(1))
        
        return files
    
    def display_file_info(self, filepath: str, index: int, total: int):
        """Display file information for review"""
        print("\n" + "="*80)
        print(f"File {index}/{total}")
        print("="*80)
        print(f"Path: {filepath}")
        
        # Extract folder name and filename
        parts = filepath.split('\\')
        if len(parts) >= 2:
            folder = parts[-2]
            filename = parts[-1]
            print(f"Folder: {folder}")
            print(f"File: {filename}")
    
    def get_user_action(self) -> tuple:
        """Get user's decision on what to do with the file"""
        print("\nOptions:")
        print("  [M] Keep as Movie (skip)")
        print("  [T] Move to TV Shows (specify destination)")
        print("  [D] Delete this file")
        print("  [Q] Quit and save actions")
        
        while True:
            choice = input("\nYour choice: ").strip().upper()
            
            if choice == 'M':
                return ('keep', '')
            elif choice == 'T':
                dest = input("Enter TV show destination path: ").strip()
                if dest:
                    return ('move', dest)
                else:
                    print("Destination cannot be empty. Try again.")
            elif choice == 'D':
                return ('delete', '')
            elif choice == 'Q':
                return ('quit', '')
            else:
                print("Invalid choice. Please enter M, T, D, or Q.")
    
    def review_files(self):
        """Main interactive review process"""
        files = self.parse_diff_file()
        
        if not files:
            print("No files found in the diff file.")
            return
        
        print(f"\nFound {len(files)} files to review.")
        
        for idx, filepath in enumerate(files, 1):
            self.display_file_info(filepath, idx, len(files))
            
            action, destination = self.get_user_action()
            
            if action == 'quit':
                print("\nStopping review...")
                break
            elif action == 'move':
                self.actions.append({
                    'action': 'move',
                    'source': filepath,
                    'destination': destination
                })
                print(f"✓ Will move to: {destination}")
            elif action == 'delete':
                self.actions.append({
                    'action': 'delete',
                    'source': filepath
                })
                print("✓ Will delete")
            elif action == 'keep':
                self.actions.append({
                    'action': 'keep',
                    'source': filepath
                })
                print("✓ Will keep as movie")
    
    def save_actions(self, output_path: str = "actions.json"):
        """Save actions to JSON file for review and execution"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.actions, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved actions to: {output_path}")
        
        # Print summary
        move_count = sum(1 for a in self.actions if a['action'] == 'move')
        delete_count = sum(1 for a in self.actions if a['action'] == 'delete')
        keep_count = sum(1 for a in self.actions if a['action'] == 'keep')
        
        print(f"\nSummary:")
        print(f"  Files to move: {move_count}")
        print(f"  Files to delete: {delete_count}")
        print(f"  Files to keep: {keep_count}")


class ActionExecutor:
    """Phase 2: Execute actions from actions.json"""
    
    def __init__(self, actions_file: str):
        self.actions_file = actions_file
        self.actions = []
        self.folders_to_check = set()
        
    def load_actions(self):
        """Load actions from JSON file"""
        with open(self.actions_file, 'r', encoding='utf-8') as f:
            self.actions = json.load(f)
        print(f"Loaded {len(self.actions)} actions from {self.actions_file}")
    
    def get_parent_folder(self, filepath: str) -> str:
        """Get the parent folder of a file"""
        return str(Path(filepath).parent)
    
    def execute_move(self, source: str, destination: str) -> tuple:
        """Move a file and track its parent folder"""
        try:
            # Ensure destination directory exists
            dest_path = Path(destination)
            if not dest_path.exists():
                dest_path.mkdir(parents=True, exist_ok=True)
            
            # Get filename and construct full destination path
            filename = Path(source).name
            full_dest = dest_path / filename
            
            print(f"Moving: {source}")
            print(f"     -> {full_dest}")
            
            shutil.move(source, str(full_dest))
            
            # Track the source folder for cleanup
            self.folders_to_check.add(self.get_parent_folder(source))
            
            return (True, None)
        except Exception as e:
            return (False, str(e))
    
    def execute_delete(self, source: str) -> tuple:
        """Delete a file and track its parent folder"""
        try:
            print(f"Deleting: {source}")
            os.remove(source)
            
            # Track the source folder for cleanup
            self.folders_to_check.add(self.get_parent_folder(source))
            
            return (True, None)
        except Exception as e:
            return (False, str(e))
    
    def cleanup_empty_folders(self):
        """Remove empty folders after file operations"""
        print("\n" + "="*80)
        print("Cleaning up empty folders...")
        print("="*80)
        
        deleted_folders = []
        errors = []
        
        for folder in sorted(self.folders_to_check):
            try:
                folder_path = Path(folder)
                if folder_path.exists() and folder_path.is_dir():
                    # Check if folder is empty
                    if not any(folder_path.iterdir()):
                        print(f"Deleting empty folder: {folder}")
                        folder_path.rmdir()
                        deleted_folders.append(folder)
                    else:
                        print(f"Skipping non-empty folder: {folder}")
            except Exception as e:
                errors.append((folder, str(e)))
                print(f"Error deleting folder {folder}: {e}")
        
        print(f"\nDeleted {len(deleted_folders)} empty folders")
        if errors:
            print(f"Failed to delete {len(errors)} folders")
    
    def execute_all(self):
        """Execute all actions from the file"""
        errors = []
        stats = {'moved': 0, 'deleted': 0, 'kept': 0, 'errors': 0}
        
        print("\n" + "="*80)
        print("Executing actions...")
        print("="*80 + "\n")
        
        for idx, action in enumerate(self.actions, 1):
            print(f"\n[{idx}/{len(self.actions)}]")
            
            action_type = action['action']
            source = action['source']
            
            if action_type == 'move':
                destination = action['destination']
                success, error = self.execute_move(source, destination)
                if success:
                    stats['moved'] += 1
                else:
                    stats['errors'] += 1
                    errors.append(('move', source, error))
                    print(f"  ERROR: {error}")
            
            elif action_type == 'delete':
                success, error = self.execute_delete(source)
                if success:
                    stats['deleted'] += 1
                else:
                    stats['errors'] += 1
                    errors.append(('delete', source, error))
                    print(f"  ERROR: {error}")
            
            elif action_type == 'keep':
                print(f"Keeping: {source}")
                stats['kept'] += 1
        
        # Clean up empty folders
        self.cleanup_empty_folders()
        
        # Print summary
        print("\n" + "="*80)
        print("EXECUTION SUMMARY")
        print("="*80)
        print(f"Files moved:   {stats['moved']}")
        print(f"Files deleted: {stats['deleted']}")
        print(f"Files kept:    {stats['kept']}")
        print(f"Errors:        {stats['errors']}")
        
        if errors:
            print("\n" + "="*80)
            print("ERRORS")
            print("="*80)
            for operation, path, error in errors:
                print(f"{operation.upper()}: {path}")
                print(f"  Error: {error}\n")


def main():
    print("="*80)
    print("Movie Folder Cleanup Script")
    print("="*80)
    print("\nThis script operates in two phases:")
    print("  Phase 1: Review files and generate actions.json")
    print("  Phase 2: Execute actions from actions.json")
    print()
    
    mode = input("Run [1] Generate actions or [2] Execute actions? ").strip()
    
    if mode == '1':
        # Phase 1: Generate actions
        # diff_file = input("\nEnter path to your diff file: ").strip()
        diff_file = "movie_differences_01.txt"
        
        if not os.path.exists(diff_file):
            print(f"Error: File not found: {diff_file}")
            return
        
        generator = ActionGenerator(diff_file)
        generator.review_files()
        generator.save_actions()
        
        print("\nNext steps:")
        print("1. Review and edit 'actions.json' if needed")
        print("2. Run this script again and choose option [2] to execute")
    
    elif mode == '2':
        # Phase 2: Execute actions
        actions_file = input("\nEnter path to actions file [actions.json]: ").strip()
        if not actions_file:
            actions_file = "actions.json"
        
        if not os.path.exists(actions_file):
            print(f"Error: File not found: {actions_file}")
            return
        
        print("\nWARNING: This will move and delete files!")
        confirm = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            executor = ActionExecutor(actions_file)
            executor.load_actions()
            executor.execute_all()
        else:
            print("Execution cancelled.")
    
    else:
        print("Invalid option. Please enter 1 or 2.")


if __name__ == "__main__":
    main()
