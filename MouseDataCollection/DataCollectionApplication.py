import time
import csv
import os
import threading
import tkinter as tk
from tkinter import messagebox
from pynput import mouse
import random
import math

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
        # Update counter on every move to feel more responsive
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
    """The interactive canvas where users perform tasks with randomized shape positions."""
    SHAPE_PADDING = 50  # Min distance from canvas edge
    SHAPE_SIZE = 20     # Radius/half-width of shapes
    
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
        self.bind("<ButtonPress-3>", self.on_right_click)
        self.bind("<Double-Button-1>", self.on_double_click)

    def _get_random_coords(self):
        """Generates random coordinates within the canvas, respecting padding."""
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = random.randint(self.SHAPE_PADDING, w - self.SHAPE_PADDING)
        y = random.randint(self.SHAPE_PADDING, h - self.SHAPE_PADDING)
        return x, y

    def next_task(self):
        self.delete("all")
        self.current_task_index += 1
        if self.current_task_index >= len(self.tasks):
            self.app_callback("task_complete", "Cycle complete! Restarting...")
            self.current_task_index = 0

        task = self.tasks[self.current_task_index]
        self.app_callback("new_task", f"Task: {task.replace('_', ' ').title()}")
        self.draw_shapes_for_task(task)

    def draw_shapes_for_task(self, task):
        x, y = self._get_random_coords()
        s = self.SHAPE_SIZE

        if task == 'left_click_triangle':
            self.shapes['triangle'] = self.create_polygon(x, y-s, x-s, y+s, x+s, y+s, fill="orange", tags="triangle")
            self.create_text(x, y - (s+15), text="Left Click Here", font=("Helvetica", 10))
        
        elif task == 'right_click_rev_triangle':
            self.shapes['rev_triangle'] = self.create_polygon(x, y+s, x-s, y-s, x+s, y-s, fill="blue", tags="rev_triangle")
            self.create_text(x, y - (s+15), text="Right Click Here", font=("Helvetica", 10))
        
        elif task == 'double_click_square':
            self.shapes['square'] = self.create_rectangle(x-s, y-s, x+s, y+s, fill="green", tags="square")
            self.create_text(x, y - (s+15), text="Double Click Here", font=("Helvetica", 10))

        elif task == 'drag_circle':
            start_x, start_y = x, y
            # Ensure the goal is a reasonable distance away
            while True:
                end_x, end_y = self._get_random_coords()
                distance = math.sqrt((start_x - end_x)**2 + (start_y - end_y)**2)
                if distance > 150: # Minimum drag distance
                    break
            
            self.shapes['circle'] = self.create_oval(start_x-s, start_y-s, start_x+s, start_y+s, fill="purple", tags="circle")
            self.shapes['goal'] = self.create_rectangle(end_x-(s+5), end_y-(s+5), end_x+(s+5), end_y+(s+5), outline="red", width=2, tags="goal")
            self.create_text(start_x, start_y - (s+15), text="Drag Me", font=("Helvetica", 10))
            self.create_text(end_x, end_y - (s+20), text="To Here", font=("Helvetica", 10))

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
        if self.drag_data["item"] is None or 'goal' not in self.shapes: return
        
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
        self.root.geometry("700x600")
        self.collector = None
        self.collector_thread = None
        self.remaining_time = 0
        self.timer_id = None
        self.setup_main_window()

    def setup_main_window(self):
        # Main Frame
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Configuration Frame
        config_frame = tk.Frame(main_frame)
        config_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(config_frame, text="Username:").grid(row=0, column=0, sticky='w', padx=5)
        self.username_entry = tk.Entry(config_frame)
        self.username_entry.grid(row=0, column=1, padx=5)
        self.username_entry.insert(0, "user1")

        tk.Label(config_frame, text="Duration (min):").grid(row=0, column=2, sticky='w', padx=5)
        self.duration_entry = tk.Entry(config_frame, width=5)
        self.duration_entry.grid(row=0, column=3, padx=5)
        self.duration_entry.insert(0, "3")
        
        self.label_var = tk.StringVar(value="Genuine")
        tk.Label(config_frame, text="User Type:").grid(row=1, column=0, sticky='w', padx=5, pady=(5,0))
        tk.Radiobutton(config_frame, text="Genuine", variable=self.label_var, value="Genuine").grid(row=1, column=1, sticky='w', pady=(5,0))
        tk.Radiobutton(config_frame, text="Imposter", variable=self.label_var, value="Imposter").grid(row=1, column=2, sticky='w', columnspan=2, pady=(5,0))

        # Canvas for tasks
        self.task_canvas = TaskCanvas(main_frame, self.app_callback, bg='lightgrey', relief=tk.SUNKEN, borderwidth=2)
        self.task_canvas.pack(expand=True, fill=tk.BOTH, pady=5)
        
        # Bottom status and control frame
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_button = tk.Button(bottom_frame, text="Start Collection", command=self.start_collection, bg="#90EE90")
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(bottom_frame, text="Stop Collection", command=self.stop_collection, state=tk.DISABLED, bg="#F08080")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.timer_label = tk.Label(bottom_frame, text="Time: 00:00", font=("Helvetica", 10, "bold"))
        self.timer_label.pack(side=tk.LEFT, padx=10)
        
        # Status Frame for right-aligned labels
        status_frame = tk.Frame(bottom_frame)
        status_frame.pack(side=tk.RIGHT)

        self.status_label = tk.Label(status_frame, text="Ready to start.", fg="blue", anchor='e')
        self.status_label.pack(fill=tk.X)
        self.counter_label = tk.Label(status_frame, text="Events: 0/128 | Blocks: 0", fg="navy", anchor='e')
        self.counter_label.pack(fill=tk.X)

    def app_callback(self, type, message):
        if type == "new_task":
            self.status_label.config(text=message)
        elif type == "task_complete":
            self.status_label.config(text=message)
            # No need to call next_task from here, it's self-contained in the canvas loop
            
    def update_status(self, message):
        self.status_label.config(text=message)

    def update_counters(self, event_count, block_count):
        self.counter_label.config(text=f"Events: {event_count % BLOCK_SIZE}/{BLOCK_SIZE} | Blocks: {block_count}")

    def countdown(self):
        if self.remaining_time > 0:
            mins, secs = divmod(self.remaining_time, 60)
            self.timer_label.config(text=f"Time: {mins:02d}:{secs:02d}")
            self.remaining_time -= 1
            self.timer_id = self.root.after(1000, self.countdown)
        else:
            self.timer_label.config(text="Time's up!")
            self.stop_collection()

    def start_collection(self):
        username = self.username_entry.get().strip()
        duration_str = self.duration_entry.get().strip()
        label = self.label_var.get()
        if not username or not duration_str.isdigit() or int(duration_str) <= 0:
            messagebox.showerror("Error", "Please enter a valid username and a positive numeric duration.")
            return

        for widget in [self.username_entry, self.duration_entry]:
            widget.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.remaining_time = int(duration_str) * 60
        self.countdown()

        self.collector = MouseDataCollector(username, label, duration_str, self.update_status, self.update_counters)
        self.collector.start()
        self.task_canvas.next_task()

    def stop_collection(self):
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        if self.collector: 
            self.collector.stop()
        
        for widget in [self.username_entry, self.duration_entry]:
            widget.config(state=tk.NORMAL)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

        self.update_counters(0, 0)
        self.task_canvas.delete("all")
        self.task_canvas.current_task_index = -1
        self.timer_label.config(text="Time: 00:00")
        self.status_label.config(text="Ready to start.")

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseApp(root)
    root.mainloop()