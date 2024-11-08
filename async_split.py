from typing import Optional, override
from dataclasses import dataclass
from queue import SimpleQueue
import time
import threading

import splitNSP

@dataclass(slots=True, frozen=True)
class InitialInfoEvent:
    total_parts: int
    total_bytes: int

@dataclass(slots=True, frozen=True) 
class StartPartEvent:
    part_number: int
    total_parts: int

@dataclass(slots=True, frozen=True) 
class FinishPartEvent:
    part_number: int
    total_parts: int

@dataclass(slots=True, frozen=True)
class FileProgressEvent:
    written_bytes: int
    total_bytes: int

@dataclass(slots=True, frozen=True)
class ArchiveBitEvent:
    error_msg: 'Optional[str]'

@dataclass(slots=True, frozen=True)
class ExceptionExitEvent:
    exc_type: type
    exc_str: str
    exc_repr: str

@dataclass(slots=True, frozen=True)
class NormalExitEvent:
    pass


class QueueSplitReporter(splitNSP.SplitReporter):
    def __init__(self, queue: SimpleQueue):
        self.queue = queue
        self.last_file_progress_time = time.time()

    @override
    def report_initial_info(self, total_parts: int, total_bytes: int):
        self.queue.put_nowait(InitialInfoEvent(total_parts, total_bytes))

    @override
    def report_start_part(self, part_number: int, total_parts: int):
        self.queue.put_nowait(StartPartEvent(part_number, total_parts))

    @override
    def report_finish_part(self, part_number: int, total_parts: int):
        self.queue.put_nowait(FinishPartEvent(part_number, total_parts))

    @override
    def report_file_progress(self, written_bytes: int, total_bytes: int):
        curr_time = time.time()
        if curr_time - self.last_file_progress_time >= 0.13:
            self.last_file_progress_time = curr_time
            self.queue.put_nowait(FileProgressEvent(written_bytes, total_bytes))

    @override
    def report_set_archive_bit(self, error_msg: 'Optional[str]'):
        self.queue.put_nowait(ArchiveBitEvent(error_msg))

class SplitterThread(threading.Thread): 
    def __init__(self, queue: SimpleQueue, input_file_path, output_parent_dir = None):
        super().__init__()
        self.queue = queue

        self.input_file_path = input_file_path
        self.output_parent_dir = output_parent_dir
        
    @override
    def run(self):
        split_reporter = QueueSplitReporter(self.queue)

        try:
            splitNSP.split(
                input_file_path=self.input_file_path,
                output_parent_dir=self.output_parent_dir,
                reporter=split_reporter)
            self.queue.put_nowait(NormalExitEvent())
        except BaseException as e:
            self.queue.put_nowait(ExceptionExitEvent(type(e), str(e), repr(e)))

@dataclass()
class SplitterState:
    queue: SimpleQueue
    thread: SplitterThread

def start_splitter_thread(input_file_path, output_parent_dir = None, queue: SimpleQueue = None) -> SplitterState:
    if queue is None:
        queue = SimpleQueue()

    state = SplitterState(queue = queue, thread = SplitterThread(queue, input_file_path, output_parent_dir))
    
    state.thread.start()
    return state