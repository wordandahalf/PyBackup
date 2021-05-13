# PyBackup
A Python script for extracting data from iOS backups

## Installation
1. Install Python. I used v3.9.5.
2. Go through the imports and ensure `magic`, `plistlib`, and `pyprind` are installed.
>   Note: `magic` is not necessary at the moment. Comment out `get_file_mime` if you don't want to bother installing it.

## Use
1. Create a backup of an iOS device
> It has only been tested with iPhones and iTunes.
2. `python3 pybackup.py -b <path to root folder of backup>`
See `python3 pybackup.py --help` for more information.
