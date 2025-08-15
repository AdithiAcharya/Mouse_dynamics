import time
import csv
import os
import threading
import tkinter as tk
from tkinter import messagebox
from pynput import mouse
import random

# --- Configuration ---
BLOCK_SIZE = 128
DIMENSIONS = 2
OUTPUT_FOLDER = "mousedatacollection"

class MouseDataCollector:
    """Handles background mouse listening and data saving."""
    def __init__(self, username, label, session_duration, status_callback, counter_callback):
        self.username = username
        self.label = label
        self.session_duration = session_duration
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        self.output_filename = os.path.join(OUTPUT_FOLDER, f"sapimouse_ABS_dx_dy_{session_duration}min.csv")
        self.events = []
        self.last_pos = None
        self.listener = None
        self.is_collecting = False
        self.block_count = 0
        self.status_callback = status_callback
        self.counter_callback = counter_callback

    def on_move(self, x, y):
        if not self.is_collecting: return
        if self.last_pos is not None:
            dx = x - self.last_pos[0]
            dy = y - self.last_pos[1]
            if dx != 0 or dy != 0:
                self.events.extend([abs(dx), abs(dy)])
                self.check_block_size()
        self.last_pos = (x, y)
        self.counter_callback(len(self.events) // DIMENSIONS, self.block_count)

    def on_click(self, x, y, button, pressed):
        if not self.is_collecting: return
        self.on_move(x, y)

    def on_scroll(self, x, y, dx, dy):
        if not self.is_collecting: return
        self.on_move(x, y)

    def check_block_size(self):
        if len(self.events) >= BLOCK_SIZE * DIMENSIONS:
            block_data = self.events[:BLOCK_SIZE * DIMENSIONS]
            self.events = self.events[BLOCK_SIZE * DIMENSIONS:]
            row_to_save = block_data + [self.username, self.label]
            with open(self.output_filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row_to_save)
            self.block_count += 1
            self.status_callback(f"Saved block #{self.block_count} for user '{self.username}'.")

    def start(self):
        self.is_collecting = True
        with mouse.Controller() as controller:
            self.last_pos = controller.position
        self.listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.listener.start()
        self.status_callback(f"Collecting data for '{self.username}'...")

    def stop(self):
        if self.listener: self.listener.stop()
        self.is_collecting = False
        self.status_callback(f"Stopped. Data saved in '{self.output_filename}'.")

class TaskCanvas(tk.Canvas):
    """The interactive canvas where users perform tasks."""
    def __init__(self, parent, app_callback, **kwargs):
        super().__init__(parent, **kwargs)
        self.app_callback = app_callback
        self.tasks = [
            'left_click_triangle', 'right_click_rev_triangle',
            'double_click_square', 'drag_circle'
        ]
        self.current_task_index = -1
        self.shapes = {}
        self.drag_data = {"x": 0, "y": 0, "item": None}

        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonPress-3>", self.on_right_click) # Right click
        self.bind("<Double-Button-1>", self.on_double_click)

    def next_task(self):
        self.delete("all") # Clear canvas
        self.current_task_index += 1
        if self.current_task_index >= len(self.tasks):
            self.app_callback("task_complete", "All tasks complete! Restarting cycle.")
            self.current_task_index = 0 # Loop back to the first task

        task = self.tasks[self.current_task_index]
        self.app_callback("new_task", f"Current Task: {task.replace('_', ' ').title()}")
        self.draw_shapes_for_task(task)

    def draw_shapes_for_task(self, task):
        # Wait for the canvas to be drawn to get its dimensions
        self.update_idletasks() 
        w, h = self.winfo_width(), self.winfo_height()
        
        if task == 'left_click_triangle':
            self.shapes['triangle'] = self.create_polygon(w/2, h/2-20, w/2-20, h/2+20, w/2+20, h/2+20, fill="orange", tags="triangle")
            self.create_text(w/2, h/2 - 40, text="Left Click Here", font=("Helvetica", 12))
        elif task == 'right_click_rev_triangle':
            self.shapes['rev_triangle'] = self.create_polygon(w/2, h/2+20, w/2-20, h/2-20, w/2+20, h/2-20, fill="blue", tags="rev_triangle")
            self.create_text(w/2, h/2 - 40, text="Right Click Here", font=("Helvetica", 12))
        elif task == 'double_click_square':
            self.shapes['square'] = self.create_rectangle(w/2-20, h/2-20, w/2+20, h/2+20, fill="green", tags="square")
            self.create_text(w/2, h/2 - 40, text="Double Click Here", font=("Helvetica", 12))
        elif task == 'drag_circle':
            self.shapes['circle'] = self.create_oval(w/4-20, h/2-20, w/4+20, h/2+20, fill="purple", tags="circle")
            self.shapes['goal'] = self.create_rectangle(3*w/4-25, h/2-25, 3*w/4+25, h/2+25, outline="red", width=2, tags="goal")
            self.create_text(w/4, h/2 - 40, text="Drag Me", font=("Helvetica", 12))
            self.create_text(3*w/4, h/2 - 40, text="To Here", font=("Helvetica", 12))


    def on_press(self, event):
        item = self.find_withtag(tk.CURRENT)
        if not item: return
        tag = self.gettags(item[0])[0]
        
        if tag == 'triangle' and self.tasks[self.current_task_index] == 'left_click_triangle':
            self.next_task()
        elif tag == 'circle' and self.tasks[self.current_task_index] == 'drag_circle':
            self.drag_data["item"] = item[0]
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def on_right_click(self, event):
        item = self.find_withtag(tk.CURRENT)
        if not item: return
        tag = self.gettags(item[0])[0]
        if tag == 'rev_triangle' and self.tasks[self.current_task_index] == 'right_click_rev_triangle':
            self.next_task()

    def on_double_click(self, event):
        item = self.find_withtag(tk.CURRENT)
        if not item: return
        tag = self.gettags(item[0])[0]
        if tag == 'square' and self.tasks[self.current_task_index] == 'double_click_square':
            self.next_task()

    def on_drag(self, event):
        if self.drag_data["item"] is None: return
        delta_x = event.x - self.drag_data["x"]
        delta_y = event.y - self.drag_data["y"]
        self.move(self.drag_data["item"], delta_x, delta_y)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_release(self, event):
        if self.drag_data["item"] is None: return
        goal_coords = self.coords(self.shapes['goal'])
        item_coords = self.coords(self.drag_data["item"])
        
        item_center_x = (item_coords[0] + item_coords[2]) / 2
        item_center_y = (item_coords[1] + item_coords[3]) / 2
        
        if goal_coords[0] < item_center_x < goal_coords[2] and \
           goal_coords[1] < item_center_y < goal_coords[3]:
            if self.tasks[self.current_task_index] == 'drag_circle':
                self.next_task()
        self.drag_data["item"] = None

class MouseApp:
    """The main GUI application class."""
    def __init__(self, root):
        self.root = root
        self.root.title("SapiMouse Task-Based Data Logger")
        self.root.geometry("600x500")
        self.collector = None
        self.collector_thread = None
        self.remaining_time = 0
        self.timer_id = None

        self.setup_main_window()

    def setup_main_window(self):
        top_frame = tk.Frame(self.root, pady=10)
        top_frame.pack(fill=tk.X)
        tk.Label(top_frame, text="Username:").pack(side=tk.LEFT, padx=(10, 5))
        self.username_entry = tk.Entry(top_frame, width=15)
        self.username_entry.pack(side=tk.LEFT, padx=5)
        self.username_entry.insert(0, "user1")

        tk.Label(top_frame, text="Duration (min):").pack(side=tk.LEFT, padx=5)
        self.duration_entry = tk.Entry(top_frame, width=5)
        self.duration_entry.pack(side=tk.LEFT, padx=5)
        self.duration_entry.insert(0, "3")

        self.label_var = tk.StringVar(value="Genuine")
        label_frame = tk.Frame(self.root)
        tk.Label(label_frame, text="User Type:").pack(side=tk.LEFT, padx=(10, 5))
        tk.Radiobutton(label_frame, text="Genuine", variable=self.label_var, value="Genuine").pack(side=tk.LEFT)
        tk.Radiobutton(label_frame, text="Imposter", variable=self.label_var, value="Imposter").pack(side=tk.LEFT)
        label_frame.pack(pady=5)

        self.task_canvas = TaskCanvas(self.root, self.app_callback, bg='lightgrey', relief=tk.SUNKEN, borderwidth=2)
        self.task_canvas.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        
        bottom_frame = tk.Frame(self.root, pady=10)
        bottom_frame.pack(fill=tk.X)
        self.start_button = tk.Button(bottom_frame, text="Start Collection", command=self.start_collection, bg="lightgreen")
        self.start_button.pack(side=tk.LEFT, padx=(10, 5))
        self.stop_button = tk.Button(bottom_frame, text="Stop Collection", command=self.stop_collection, state=tk.DISABLED, bg="lightcoral")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.timer_label = tk.Label(bottom_frame, text="Time: 00:00", font=("Helvetica", 10, "bold"))
        self.timer_label.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(bottom_frame, text="Ready to start.", fg="blue")
        self.status_label.pack(side=tk.RIGHT, padx=10)
        self.counter_label = tk.Label(bottom_frame, text="Events: 0/128 | Blocks: 0", fg="navy")
        self.counter_label.pack(side=tk.RIGHT, padx=10)

    def app_callback(self, type, message):
        if type == "new_task":
            self.status_label.config(text=message)
        elif type == "task_complete":
            self.status_label.config(text=message)
            self.task_canvas.next_task()

    def update_status(self, message):
        self.status_label.config(text=message)

    def update_counters(self, event_count, block_count):
        self.counter_label.config(text=f"Events: {event_count}/{BLOCK_SIZE} | Blocks: {block_count}")

    def countdown(self):
        if self.remaining_time > 0:
            mins, secs = divmod(self.remaining_time, 60)
            time_str = f"Time: {mins:02d}:{secs:02d}"
            self.timer_label.config(text=time_str)
            self.remaining_time -= 1
            self.timer_id = self.root.after(1000, self.countdown)
        else:
            self.timer_label.config(text="Time's up!")
            self.stop_collection()

    def start_collection(self):
        username = self.username_entry.get().strip()
        duration_str = self.duration_entry.get().strip()
        label = self.label_var.get()
        if not username or not duration_str.isdigit():
            messagebox.showerror("Error", "Please enter a valid username and a numeric duration.")
            return

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.username_entry.config(state=tk.DISABLED)
        self.duration_entry.config(state=tk.DISABLED)
        
        self.remaining_time = int(duration_str) * 60
        self.countdown() # Start the timer

        self.collector = MouseDataCollector(username, label, duration_str, self.update_status, self.update_counters)
        self.collector.start()
        self.task_canvas.next_task()

    def stop_collection(self):
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

        if self.collector: self.collector.stop()
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.username_entry.config(state=tk.NORMAL)
        self.duration_entry.config(state=tk.NORMAL)
        self.update_counters(0, 0)
        self.task_canvas.delete("all")
        self.task_canvas.current_task_index = -1
        self.timer_label.config(text="Time: 00:00")


if __name__ == "__main__":
    root = tk.Tk()
    app = MouseApp(root)
    root.mainloop()
