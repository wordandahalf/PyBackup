# PyBackup
A Python script for extracting data from iOS backups

## Installation
1. Install Python. I used v3.9.5.
2. Ensure `pathvalidate`, `plistlib`, `pyprind`, and `tabulate` are installed.

## Use
1. Create a backup of an iOS device
> It has only been tested with iPhones and iTunes.
2. `python3 pybackup.py -b <path to root folder of backup>`
See `python3 pybackup.py --help` for more information.
