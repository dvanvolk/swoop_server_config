import os

import os

def get_all_files_recursive(directory_path):
    """
    Returns a list of all files in the specified directory and its subdirectories.
    """
    files = []
    for root, _, filenames in os.walk(directory_path):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files

# Example usage:
directory = r"\\192.168.10.45\TVShows"  # Replace with your directory path
all_files = get_all_files_recursive(directory)
with open("tvshows.txt", "w", encoding="utf-8") as file:
    for item in all_files:
        file.write(str(item) + "\n")
print(all_files)