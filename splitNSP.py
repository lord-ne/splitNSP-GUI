#!/usr/bin/env python3
# Original Author: AnalogMan (modified by lord_ne)
# Purpose: Splits Nintendo Switch NSP files into parts for installation on FAT32

# Note: This script can be run stand-alone without any packages installed

import argparse
import math
import os
import platform
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
from typing import override

class SplitReporter:
    def report_initial_info(self, total_parts: int, total_bytes: int):
        pass

    def report_start_part(self, part_number: int, total_parts: int):
        pass

    def report_finish_part(self, part_number: int, total_parts: int):
        pass

    def report_file_progress(self, written_bytes: int, total_bytes: int):
        pass

# This method makes a best-effort to set the archive bit, but on many operating systems it will not succeed
def _try_set_archive_bit(folder: Path):
    try:
        if platform.system == 'Windows':
            subprocess.run(['attrib', '+a', os.path.realpath(folder)], check=True)
        else:
            os.chflags(os.stat(folder) | stat.SF_ARCHIVED)
    except Exception as e:
        print(f'Could not set archive bit ({e})')
        return False

    return True

def split(*, input_file_path: Path | str, output_parent_dir: Optional[Path | str] = None, output_dir: Optional[Path | str] = None, reporter: SplitReporter):

    # Constants

    PART_SIZE = 0xFFFF0000 # 4,294,901,760 bytes
    CHUNK_SIZE = 0x8000 # 32,768 bytes

    # Argument types and default values

    if not isinstance(input_file_path, Path):
        input_file_path = Path(input_file_path)

    if output_dir is None:
        output_name = f'{input_file_path.stem}_split{input_file_path.suffix}'
        if output_parent_dir is None:
            output_dir = input_file_path.with_name(output_name)
        else:
            output_dir = Path(output_parent_dir) / output_name
    elif not isinstance(output_dir, Path):
        output_dir = Path(output_dir)

    # Validation

    if not input_file_path.is_file():
        raise ValueError(f'{input_file_path} is not a file')

    if not output_dir.exists():
        os.makedirs(output_dir)
    else:
        if not output_dir.is_dir():
            raise ValueError(f'{output_dir} is not a folder')
        elif not (len(os.listdir(output_dir)) == 0):
            raise ValueError(f'{output_dir} is not empty')

    input_file_size = os.path.getsize(input_file_path)
    info = shutil.disk_usage(os.path.dirname(os.path.abspath(input_file_path)))
    if info.free < input_file_size * 2:
        raise ValueError('Not enough free space to run. Will require twice the space as the NSP file')

    if input_file_size <= PART_SIZE:
        raise ValueError('This NSP is under 4GiB and does not need to be split.')

    total_parts = math.ceil(input_file_size / PART_SIZE)

    reporter.report_initial_info(total_parts, input_file_size)

    # Open source file and begin writing to output files stoping at PART_SIZE
    total_written = 0
    with open(input_file_path, 'rb') as in_file:
        for i in range(total_parts):
            reporter.report_start_part(i, total_parts)
            this_part_size = min(PART_SIZE, input_file_size - total_written)
            this_part_written = 0
            with open(output_dir / f'{i:02}', 'wb') as out_file:
                while this_part_written < this_part_size:
                    this_chunk_size = min(CHUNK_SIZE, this_part_size - this_part_written)
                    out_file.write(in_file.read(this_chunk_size))
                    this_part_written += this_chunk_size
                    total_written += this_chunk_size
                    reporter.report_file_progress(total_written, input_file_size)
            reporter.report_finish_part(i, total_parts)

    _try_set_archive_bit(output_dir)

class _ProgressBarSplitReporter(SplitReporter):
    def __init__(self):
        self.last_line_length = 0
        self.last_print_time = time.time()

    def _printmsg(self, msg: str, end: str = '\n'):
        print(f'{msg:<{self.last_line_length}}', end = end)
        sys.stdout.flush()

    @override
    def report_initial_info(self, total_parts: int, total_bytes: int):
        self._printmsg(f'Splitting NSP of size {total_bytes:,d} bytes into {total_parts} parts...')

    @override
    def report_start_part(self, part_number: int, total_parts: int):
        self._printmsg(f'Starting part {part_number + 1:02} of {total_parts:02}')

    @override
    def report_finish_part(self, part_number: int, total_parts: int):
        self._printmsg(f'Part {part_number + 1:02} of {total_parts:02} complete')

    @override
    def report_file_progress(self, written_bytes: int, total_bytes: int):
        curr_time = time.time()
        if curr_time - self.last_print_time < 0.05:
            return

        self.last_print_time = curr_time

        total_string = f'{total_bytes:,d}'
        written_string = f'{written_bytes:{len(total_string)},d}'
        msg = f'   {written_string} / {total_string} bytes'
        this_line_length = len(msg)

        self._printmsg(msg, end='\r')

        self.last_line_length = this_line_length

def _main():
    print('\n========== NSP Splitter ==========\n')

    # Arg parser for program options
    parser = argparse.ArgumentParser(description='Split NSP/XCI files into FAT32 compatible sizes')
    parser.add_argument('input_file_path', help='Path to NSP or XCI file')
    parser.add_argument('-o', '--output-dir', type=str, default=None, help='Set alternative output dir')

    args = parser.parse_args()

    try:
        split(input_file_path = args.input_file_path,
            output_dir = args.output_dir,
            reporter=_ProgressBarSplitReporter())
    except Exception as e:
        print(e)
        return 1

    print('\n============== Done ==============\n')

if __name__ == '__main__':
    _main()