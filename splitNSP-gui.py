import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as tkfd
from pathlib import Path
import queue

import async_split as aspl

class FilePicker(tk.Frame):
    def __init__(self, parent, label, dir_mode = False, starting_dir=Path.home()):
        tk.Frame.__init__(
            self,
            parent,
            highlightbackground="black",
            highlightthickness=1)
        
        self.dir_mode = dir_mode
        self.last_used_dir = starting_dir
        
        padding = { "padx": 5, "pady": 5}

        self.label = ttk.Label(self, text=label)
        self.bottom_frame = tk.Frame(self)

        self.file_text = tk.StringVar()
        self.entry = ttk.Entry(self.bottom_frame, width=50, textvariable=self.file_text)
        self.button = ttk.Button(self.bottom_frame, text="📁", command=self._pick_file, width=2)

        self.label.pack(side=tk.TOP, anchor=tk.W, **padding)
        self.bottom_frame.pack(side=tk.TOP, anchor=tk.W, fill=tk.X, expand=True, **padding)

        self.button.pack(side=tk.LEFT, anchor=tk.N, **padding)
        self.entry.pack(side=tk.LEFT, anchor=tk.N, fill=tk.X, expand=True, **padding)

    def _pick_file(self):
        if self.dir_mode:
            chosen_file = tkfd.askdirectory(
                initialdir=self.last_used_dir,
                mustexist=True)
        else:
            chosen_file = tkfd.askopenfilename(
                initialdir=self.last_used_dir,
                filetypes=[("Nintendo Switch game files", "*.xci *.nsp"), ("All files", "*")])

        if chosen_file:
            path = Path(chosen_file).absolute()
            self.last_used_dir = path.parent
            self.file_text.set(path)

    def curr_file(self):
        return Path(self.file_text.get()).absolute()

def add_periodic_funcion(root: tk.Tk, period, func, /, *args):
    def poll():
        func(*args)
        root.after(period, poll)

    root.after(0, poll)

def main():
    root = tk.Tk()
    root.title("splitNSP-GUI")

    input_file_picker = FilePicker(root, label="Choose a file to split", dir_mode=False)
    input_file_picker.pack(side=tk.TOP, padx=16, pady=16, fill=tk.X)

    output_dir_picker = FilePicker(root, label="Choose an output directory", dir_mode=True)
    output_dir_picker.pack(side=tk.TOP, padx=16, pady=16, fill=tk.X)
    
    tk.Button(root, text="Start", command=lambda: start_splitting()).pack(side=tk.TOP, padx=16, pady=16)
    
    separator = ttk.Separator(root).pack(side=tk.TOP, fill=tk.X)

    text_above_progressbar = tk.StringVar(root)
    ttk.Label(root, textvariable=text_above_progressbar).pack(side=tk.TOP, fill=tk.X)

    progressbar_progress = tk.DoubleVar(root)
    ttk.Progressbar(root, variable=progressbar_progress, maximum=1.0).pack(side=tk.TOP, padx=16, pady=16, fill=tk.X)

    split_state: aspl.SplitterState = None

    def start_splitting():
        nonlocal split_state, input_file_picker, output_dir_picker
        if split_state is not None:
            # TODO: Show error message of some kind?
            return

        split_state = aspl.start_splitter_thread(
            input_file_picker.curr_file(),
            output_dir_picker.curr_file())

    def update_state():
        nonlocal split_state, progressbar_progress, text_above_progressbar

        if split_state is None:
            return
        
        while True:
            try:
                match split_state.queue.get_nowait():
                    case aspl.InitialInfoEvent(total_parts, total_bytes):
                        print(f'Splitting NSP of size {total_bytes:,d} bytes into {total_parts} parts...')
                        text_above_progressbar.set("Splitting")
                        progressbar_progress.set(0.0)

                    case aspl.StartPartEvent(part_number, total_parts):
                        print(f'Starting part {part_number + 1:02} of {total_parts:02}')
                        text_above_progressbar.set(f"Splitting (part {part_number + 1} of {total_parts})")

                    case aspl.FinishPartEvent(part_number, total_parts):
                        print(f'Part {part_number + 1:02} of {total_parts:02} complete')
                    case aspl.FileProgressEvent(written_bytes, total_bytes):
                        progressbar_progress.set(float(written_bytes) / float(total_bytes))
                    case aspl.ArchiveBitEvent(error_msg):
                        if not error_msg:
                            print('Succesfully set archive bit')
                        else:
                            print(f'Could not set archive bit ({error_msg})')
                        # TODO: Show error popup on error?
                        pass
                    case aspl.ExceptionExitEvent(exc_type, exc_str, exc_repr):
                        print(f"Failed to split ({exc_str})")
                        text_above_progressbar.set("Failed to split")
                        split_state = None
                        break
                        # TODO: Show error popup on error?
                    case aspl.NormalExitEvent:
                        print("Finished splitting")
                        text_above_progressbar.set("Done")
                        progressbar_progress.set(1.0)
                        split_state = None
                        break

            except queue.Empty:
                break
    

    add_periodic_funcion(root, 240, update_state)
    root.mainloop()
    
if __name__ == "__main__":
    main()