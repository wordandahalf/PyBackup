import argparse
from enum import Enum
import json
from types import FunctionType
import magic
import os
import pathlib
import plistlib
import pyprind
import shutil
import sqlite3
import sys

def get_file_mime(path: str) -> str:
    return magic.from_file(path, mime=True)

def parse_backup(backup_path: str) -> dict:
    file_information = {}

    files = list(pathlib.Path(backup_path).rglob('*'))
    file_count = len(files)

    bar = pyprind.ProgBar(file_count)
    for file in list(pathlib.Path(backup_path).rglob('*')):
        if not file.is_dir():
            file_information[file.name] = { 'path': os.path.relpath(file, backup_path) } # MIME is unneeded (for now): , 'mime': get_file_mime(str(file)) }
        bar.update()

    return file_information

class ParsedBackup():
    path: str = ""
    found_files: dict = {}
    files: sqlite3.Cursor = None

    info: dict = {}
    manifest: dict = {}
    status: dict = {}

    def __init__(self, path: str, found_files: dict):
        self.path = path
        self.found_files = found_files

        self.info = self.__parse_plist__(os.path.join(path, 'Info.plist'))
        self.manifest = self.__parse_plist__(os.path.join(path, 'Manifest.plist'))
        self.status = self.__parse_plist__(os.path.join(path, 'Status.plist'))

        con = sqlite3.connect(os.path.join(path, 'Manifest.db'))
        self.files = con.cursor()

    def __parse_plist__(self, path: str) -> dict:
        data = {}

        with open(path, 'rb') as plist:
            data = plistlib.load(plist)
            plist.close()

        return data

def extract_camera_roll(backup: ParsedBackup, destination: str):
    # Photos have a few different possible extensions, though with one commonality:
    # they are stored in Media/DCIM/%APPLE/%.

    print("Extracting Camera Roll...")

    backup.files.execute("SELECT * FROM Files WHERE relativePath like 'Media/DCIM/%APPLE/%';")
    files = backup.files.fetchall()

    bar = pyprind.ProgBar(len(files))
    for file in files:
        fileID = file[0]
        absoluteSource = os.path.join(backup.path, backup.found_files[fileID]['path'])

        relativeDestination = file[2].replace('/', os.path.sep)
        absoluteDestination = os.path.join(destination, relativeDestination)

        os.makedirs(os.path.dirname(absoluteDestination), exist_ok=True)
        shutil.copy(absoluteSource, absoluteDestination)
        bar.update()

def extract_messages(backup: ParsedBackup, destination: str):
    pass

class FileType(Enum):
    all = ('all', None)
    photos = ('camera_roll', extract_camera_roll)
    messages = ('messages', extract_messages)

    def __str__(self):
        return self.value[0]
    
    def get_extractor(self) -> FunctionType:
        return self.value[1]

def extract_files(type: FileType, backup: ParsedBackup, destination: str):
    print(f"Extracting '{type}' to '{destination}'...")

    if type is FileType.all:
        # Iterate over each FileType except the first, which is 'all'
        for t in list(FileType)[1:]:
            t.get_extractor()(backup, destination)
    else:
        type.get_extractor()(backup, destination)
            

def main(args: list[str]):
    # Parse arguments
    parser = argparse.ArgumentParser(description='pybackup.py: The Python-based backup extractor for iOS devices.')
    parser.add_argument('--override', '-o', dest='override', type=bool, default=False)
    parser.add_argument('--backup', '-b', dest='path', help='The path to the iOS backup.', required=True)
    parser.add_argument('--extract', '-e', dest='extract_type', help=f"Type of files to extract. Valid options: {list(FileType)}. Defaults to '{FileType.all}'.", type=FileType, choices=list(FileType), default=FileType.all)
    parser.add_argument('--destination', '-d', dest='destination', help='The path to put the extracted files.', default='.')

    # Ignore the first argument, it's always the name of the file.
    opts = parser.parse_args(args[1:])

    # Verify the provided backup path
    if not os.path.isdir(opts.path):
        raise ValueError(f"The provided path '{opts.path}' does not exist or is not a folder!")

    # Check if the backup has already been parsed...
    json_file = os.path.join(opts.path, 'pybackup.json')
    files = {}

    # If not, parse the backup
    if not os.path.isfile(json_file):
        print("PyBackup file does not exist, parsing backup...")
        files = parse_backup(opts.path)
        print(f"Parsed {len(files.keys())} files!")
        print()

        with open(json_file, 'w') as file:
            file.write(json.dumps(files))
            file.close()
    else:
        with open(json_file, 'r') as file:
            files = json.load(file)
            file.close()
            
    # Otherwise, proceed with extracting the files...
    backup = ParsedBackup(opts.path, files)

    print(f"Found backup (v{backup.status['Version']}) from '{backup.info['Device Name']}' (#{backup.info['Serial Number']}, {backup.info['Product Type']}) with iOS {backup.info['Product Version']}!")

    if not opts.override and backup.status['Version'] != '3.3':
        print("Warning! This tool has only been tested with v3.3 of the iOS backup format. It may not function properly!")
        print("Pass '--override' or '-o' to override this safety mechanism.")
        sys.exit(-1)

    extract_files(opts.extract_type, backup, opts.destination)

if __name__ == '__main__':
    main(sys.argv)
