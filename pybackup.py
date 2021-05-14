import argparse
import json
from json.decoder import JSONDecodeError
import os
from pathlib import Path
from pathvalidate import sanitize_filepath
import plistlib
import pyprind
import shutil
import sqlite3
import sys
from tabulate import tabulate
from time import sleep
from types import FunctionType

class ParsedBackup():
    path: Path = None
    found_files: dict = {}
    files: sqlite3.Cursor = None

    info: dict = {}
    manifest: dict = {}
    status: dict = {}

    def __init__(self, path: Path, found_files: dict):
        self.path = path
        self.found_files = found_files

        self.info = self.__parse_plist__(path / 'Info.plist')
        self.manifest = self.__parse_plist__(path / 'Manifest.plist')
        self.status = self.__parse_plist__(path / 'Status.plist')

        con = sqlite3.connect(path / 'Manifest.db')
        self.files = con.cursor()

    def pretty_print_information(self):
        print(tabulate(
            [
                ["Device Name: " + self.info['Device Name'], "Device Type: " + self.info['Product Type']],
                ["Software Version: " + self.info['Product Version'], "Serial Number: " + self.info['Serial Number']],
                ["Backup Version: " + self.status['Version'], "Backup Date: " + self.status['Date'].strftime("%A, %d %b %Y %I:%M:%S UTC")],
                [f"Type: {'Full' if self.status['IsFullBackup'] else 'Not full'}", "Status: " + self.status['BackupState']],
                ["Encrypted: " + str(self.manifest['IsEncrypted']), ""],
            ]
        ))

    @staticmethod
    def from_path(backup_path: Path):
        json_file = backup_path / 'pybackup.json'
        json_data = {}

        if not json_file.is_file():
            print("Parsing backup...")
            files = list(backup_path.rglob('*'))
            file_count = len(files)

            bar = pyprind.ProgBar(file_count)
            for file in files:
                if not file.is_dir():
                    json_data[file.name] = { 'path': os.path.relpath(file, backup_path) }
                bar.update()

            with open(json_file, 'w') as file:
                file.write(json.dumps(json_data))
                file.close()
        else:
            with open(json_file, 'r') as file:
                try:
                    json_data = json.load(file)
                except JSONDecodeError:
                    print(f"There was an error decoding the JSON file at {json_file}. Please delete it and re-parse the backup.")

                file.close()

        return ParsedBackup(backup_path, json_data)

    @staticmethod
    def __parse_plist__(path: Path) -> dict:
        data = {}

        with Path.open(path, 'rb') as plist:
            data = plistlib.load(plist)
            plist.close()

        return data

class Extractors():
    @staticmethod
    def from_name(name: str) -> FunctionType:
        return Extractors.__mapping[name]

    @staticmethod
    def list() -> list[str]:
        return Extractors.__mapping.keys()

    def __extract_all__(backup: ParsedBackup, destination: Path):
        backup.files.execute("SELECT * FROM Files;")
        Extractors.__copy_files__(backup, backup.files.fetchall(), destination)

    def __extract_camera_roll__(backup: ParsedBackup, destination: Path):
        # Photos have a few different possible extensions, though with one commonality:
        # they are stored in Media/DCIM/%APPLE/%.

        print("Extracting Camera Roll...")

        backup.files.execute("SELECT * FROM Files WHERE relativePath like 'Media/DCIM/%APPLE/%';")
        Extractors.__copy_files__(backup, backup.files.fetchall(), destination)

    @staticmethod
    def __copy_files__(backup: ParsedBackup, files: list, destination: Path):
        bar = pyprind.ProgBar(len(files))
        for file in files:
            fileID = file[0]

            # Need to investigate this:
            if not fileID in backup.found_files:
            #    print(f"File {fileID} exists in Manifest.db, but not in pybackup.json!")
                continue

            absoluteSource = backup.path / backup.found_files[fileID]['path']
            absoluteDestination : Path = destination / sanitize_filepath(file[2])

            os.makedirs(os.path.dirname(absoluteDestination), exist_ok=True)

            shutil.copy(absoluteSource, absoluteDestination)
            bar.update()

    __mapping = {
        'all': __extract_all__,
        'camera_roll': __extract_camera_roll__
    }

def main(args: list[str]):
    # Parse arguments
    parser = argparse.ArgumentParser(description='pybackup.py: The Python-based backup extractor for iOS devices.')
    parser.add_argument('--override', '-o', dest='override', type=bool, default=False)
    parser.add_argument('--backup', '-b', dest='path', help='The path to the iOS backup.', required=True)
    parser.add_argument('--extract', '-e', dest='extract_type', help=f"Type of files to extract.", type=str, choices=Extractors.list())
    parser.add_argument('--destination', '-d', dest='destination', help='The path to put the extracted files.', default='.')

    # Ignore the first argument, it's always the name of the file.
    opts = parser.parse_args(args[1:])

    # Verify the provided backup path
    if not os.path.isdir(opts.path):
        raise ValueError(f"The provided path '{opts.path}' does not exist or is not a folder!")

    # Check if the backup has already been parsed...
    backup = ParsedBackup.from_path(Path(opts.path).resolve())

    # Otherwise, proceed with extracting the files...
    backup.pretty_print_information()

    if backup.manifest['IsEncrypted']:
        print("Warning! Backup is encrypted: the extracted files are going to appear as if they are corrupted.")
        print("Decryption will be automatically supported at a future time.")
        sleep(1)

    # Print a message if the found backup is not a version that has been tested against
    if not opts.override and backup.status['Version'] != '3.3':
        print(f"Warning! This tool has only been tested with v3.3 of the iOS backup format. It may not function properly with version v{backup.status['Version']}!")
        print("Pass '--override' or '-o' to override this safety mechanism.")
        sys.exit(-1)

    if getattr(opts, 'extract_type') is not None:
        try:
            Extractors.from_name(opts.extract_type)(backup, Path(opts.destination).resolve())
        except KeyError:
            print(f"'{opts.extract_type}' is not a valid extraction type!")

if __name__ == '__main__':
    main(sys.argv)
