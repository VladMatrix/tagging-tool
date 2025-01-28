from __future__ import annotations

import json
import os
import tkinter as tk
import platform
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from constants import __VERSION__, MAX_COLORS, IMG_SCALES, IMG_FILES, PT_SELECTED_EXTRA_SIZE, PT_BASE_SIZE, \
    PT_ZOOM_SCALE_FACTOR, \
    INTERVAL_SAVE, INTERVAL_POLL, PointsType, PT_OUTLINE_WIDTH, NEUTRAL_ZOOM_IDX
from utils import generate_rainbow_colors, generate_image_pyramid, put_image_on_canvas, get_canvas_position, \
    apply_image_scaling, in_canvas_coords, in_image_coords, Canvas, reset_canvases, format_tag, make_pairs, \
    read_tags_file, get_tag_name_convention, find_closest, get_centered_oval_bbox, get_display_dir


class ImageTaggingTool:
    def __init__(self, small_window: bool, tiny_window: bool):
        self.debug = False
        self._save_scheduler_id = None
        self._poll_scheduler_id = None

        self.root = tk.Tk()
        RES_W, RES_H = self.root.wm_maxsize()
        if RES_W < 1400 or tiny_window:
            CANVAS_W = 520
            CANVAS_H = 480
            TAG_W = 20
        elif RES_W <= 1920 or small_window:
            CANVAS_W = 800
            CANVAS_H = 800
            TAG_W = 22
        else:
            CANVAS_W = 1100
            CANVAS_H = 1100
            TAG_W = 26

        self.root.title("Image Correspondence Tagging Tool")
        self.root.geometry(f"{RES_W}x{RES_H}")
        self.root_bg_color = self.root.cget("bg")

        if platform.system() == "Windows":
            self.root.state("zoomed")  # Maximized for Windows
        elif platform.system() == "Linux":
            self.root.attributes("-zoomed", True)  # Maximized for Linux

        self.colors = generate_rainbow_colors(MAX_COLORS)

        self.tag_mode = True
        self.points: list[PointsType] = []
        self.all_tags: dict[str, list[PointsType]] = {}
        self.current_pair: str | None = None
        self.image_pairs: list[tuple[str, str]] = []
        self.reverse_file_index: dict[str, int] = {}
        self.file_index: dict[int, str] = {}
        self.loading_done = False
        self.data_dir = None
        self.suppress_select_event = False
        self.pan_start_x = 0
        self.pan_start_y = 0

        # Brand version label
        tk.Label(self.root, text=f"V{__VERSION__}", font=("Arial", 12)).grid(row=7, column=0, sticky='sw',
                                                                             padx=10, pady=0)

        # Navigation buttons
        self.button_prev = tk.Button(self.root, text="<< Z  ", command=self.prev_pair, state=tk.DISABLED)
        self.button_prev.grid(row=6, column=3, sticky='se')
        self.button_next = tk.Button(self.root, text="  X >>", command=self.next_pair, state=tk.DISABLED)
        self.button_next.grid(row=6, column=5, sticky='sw', ipadx=0)

        # Files Frame
        self.files_frame = tk.Frame(self.root, bg="lightgrey", padx=5, pady=2)
        self.files_frame.grid(row=8, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        self.button_load_images = tk.Button(self.files_frame, text="Select Image Folder",
                                            command=self.load_image_pairs_and_tags)
        self.button_load_images.pack(side="left")

        self.directory_label = tk.Label(self.files_frame, text="", font=("Arial", 12), padx=5, bg="lightgrey")
        self.directory_label.pack(side="left")

        self.dropdown = ttk.Combobox(self.files_frame, values=[])
        self.dropdown.pack(side="right", fill="both", expand=True, padx=5)
        self.dropdown.bind("<<ComboboxSelected>>", self.on_pair_selected)
        self.dropdown.config(state=tk.DISABLED)

        # Tags Frame
        self.tags_frame = tk.Frame(self.root)
        self.tags_frame.grid(row=0, rowspan=6, column=10, sticky='nsew', padx=5)

        self.tag_list_label = tk.Label(self.tags_frame, bg='lightgrey', text="Tagged Points",
                                       font=("Arial", 16, "bold"))
        self.tag_list_label.pack(side="top", anchor='n', pady=2)

        self.tag_list = tk.Listbox(self.tags_frame, selectmode=tk.SINGLE, font=("Arial", 14), width=TAG_W)
        self.tag_list.pack(expand=True, fill="both")
        self.tag_list.bind("<<ListboxSelect>>", self.on_tag_selected_from_list)
        self.tag_list.bind("<Button-1>", self.clear_tag_selection_inside)
        self.tag_list.bind("<Delete>", self.delete_tag)

        self.loading_label = tk.Label(self.tags_frame, text="", bg=self.root_bg_color,
                                      font=("Arial", 18, "bold italic"))
        self.loading_label.pack(side='bottom', anchor='s', pady=1)

        self.button_clear_all = tk.Button(self.tags_frame, text="Clear All", command=self.clear_all_tags, width=20)
        self.button_clear_all.pack(side='bottom', pady=5)
        self.button_clear_all.config(state=tk.DISABLED)

        # Canvas Frame for the first image
        self.canvas0_frame = tk.Frame(self.root)
        self.canvas0_frame.grid(row=0, rowspan=6, column=0, columnspan=4, sticky='nsew', padx=5)

        self.img0_label = tk.Label(self.canvas0_frame, bg='light grey', text="Image 1", font=("Arial", 18))
        self.img0_label.pack(side="top", fill='x', padx=5)

        self.canvas0 = Canvas(self.canvas0_frame, bg="white", width=CANVAS_W, height=CANVAS_H,
                              borderwidth=0, highlightthickness=0)
        self.canvas0.pack(expand=True)

        self.canvas0.tag_text = tk.Label(self.canvas0_frame, text="", font=("Arial", 20, "bold"), fg="black")
        self.canvas0.tag_text.pack(side='bottom')

        self.img0_cursor_txt = tk.Label(self.canvas0_frame, text="", font=("Arial", 18))
        self.img0_cursor_txt.pack(side="bottom", anchor='sw')

        # Canvas Frame for the second image
        self.canvas1_frame = tk.Frame(self.root)
        self.canvas1_frame.grid(row=0, rowspan=6, column=5, columnspan=4, sticky='nsew', padx=5)

        self.img1_label = tk.Label(self.canvas1_frame, bg='light grey', text="Image 2", font=("Arial", 18))
        self.img1_label.pack(side="top", fill='x', padx=5)

        self.canvas1 = Canvas(self.canvas1_frame, bg="white", width=CANVAS_W, height=CANVAS_H,
                              borderwidth=0, highlightthickness=0)
        self.canvas1.pack(expand=True)

        self.canvas1.tag_text = tk.Label(self.canvas1_frame, text="", font=("Arial", 20, "bold"), fg="black")
        self.canvas1.tag_text.pack(side='bottom')

        self.img1_cursor_txt = tk.Label(self.canvas1_frame, text="", font=("Arial", 18))
        self.img1_cursor_txt.pack(side="bottom", anchor='sw')

        # Link canvases
        self.canvas0.twin = self.canvas1
        self.canvas1.twin = self.canvas0

        # Bind mouse events for panning, zooming and tagging
        self.canvas0.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas0.bind("<ButtonPress-3>", self.undo_point)
        self.canvas0.bind("<B1-Motion>", self.pan_image)
        self.canvas0.bind("<MouseWheel>", self.zoom)  # For Windows/macOS
        self.canvas0.bind("<Button-4>", self.scale_up)  # For Linux scroll up
        self.canvas0.bind("<Button-5>", self.scale_down)  # For Linux scroll down

        self.canvas1.bind("<ButtonPress-1>", self.on_canvas_click)
        self.canvas1.bind("<ButtonPress-3>", self.undo_point)
        self.canvas1.bind("<B1-Motion>", self.pan_image)
        self.canvas1.bind("<MouseWheel>", self.zoom)  # For Windows/macOS
        self.canvas1.bind("<Button-4>", self.scale_up)  # For Linux scroll up
        self.canvas1.bind("<Button-5>", self.scale_down)  # For Linux scroll down

        # Bind key presses
        self.root.bind("<FocusOut>", self.on_focus_out)
        self.root.bind("q", self.quit_event)
        self.root.bind("Q", self.quit_event)
        self.root.bind("<Escape>", self.quit_event)

        self.root.bind("<Left>", lambda event: self.prev_pair())
        self.root.bind("z", lambda event: self.prev_pair())
        self.root.bind("Z", lambda event: self.prev_pair())
        self.root.bind("<Right>", lambda event: self.next_pair())
        self.root.bind("x", lambda event: self.next_pair())
        self.root.bind("X", lambda event: self.next_pair())

        self.root.bind("<KeyPress-Control_L>", self.mode_switch)
        self.root.bind("<KeyPress-Control_R>", self.mode_switch)
        self.root.bind("<KeyRelease-Control_L>", self.mode_switch)
        self.root.bind("<KeyRelease-Control_R>", self.mode_switch)

        self.root.bind("<KeyPress-space>", self.confirm_tag)
        self.root.bind("<ButtonPress-1>", self.on_click)

        self.root.mainloop()

    def reset(self):
        if self._save_scheduler_id is not None:
            self.root.after_cancel(self._save_scheduler_id)
            self._save_scheduler_id = None

        if self._poll_scheduler_id is not None:
            self.root.after_cancel(self._poll_scheduler_id)
            self._poll_scheduler_id = None

        self.tag_mode = True
        self.points = []
        self.all_tags = {}
        self.current_pair = None
        self.image_pairs = []
        self.reverse_file_index = {}
        self.file_index = {}
        self.loading_done = False
        self.data_dir = None
        self.pan_start_x = 0
        self.pan_start_y = 0

        self.directory_label.configure(text="", bg="lightgray")

        self.dropdown['values'] = []
        self.dropdown.config(state=tk.DISABLED)

    def load_image_pairs_and_tags(self):
        # check in case file selection is canceled by user
        if (image_dir := filedialog.askdirectory(title="Select Data Folder")) == "":
            return

        files = os.listdir(image_dir)
        image_files = list(filter(lambda x: x.lower().endswith(IMG_FILES), files))

        pari_status, pairs_result = make_pairs(image_files)
        if not pari_status:
            messagebox.showerror("Error", pairs_result)
            return

        name = get_tag_name_convention(image_dir)
        tags_status, tags_result = read_tags_file(os.path.join(image_dir, name))
        if not tags_status:
            messagebox.showerror("Error", tags_result)
            return

        # once everything is open, we can proceed to reset state and load everything
        self.reset()
        self.data_dir = image_dir
        self.directory_label.configure(text=get_display_dir(image_dir), bg=self.root_bg_color)

        for idx, (img0, img1) in enumerate(pairs_result):
            self.image_pairs.append((os.path.join(image_dir, img0),
                                     os.path.join(image_dir, img1)))
            base_img_name = os.path.splitext(img0)[0][:-2]
            self.file_index[idx] = base_img_name
            self.reverse_file_index[base_img_name] = idx

        self.dropdown['values'] = list(self.file_index.values())
        self.all_tags = tags_result.get('all_tags', {})
        pair_to_load = tags_result.get('open_pair_name', "")
        if pair_to_load not in self.reverse_file_index:
            pair_to_load = self.file_index[0]

        self._save_scheduler_id = self.root.after(INTERVAL_SAVE, self.save_tags)
        self.dropdown.config(state="readonly")
        self.load_selected_pair(name=pair_to_load)

    def on_pair_selected(self, event):
        combo: ttk.Combobox = event.widget
        name = combo.get()
        self.load_selected_pair(name=name)

    def load_selected_pair(self, *, name: str):
        self.loading_label.configure(text="Loading")
        self.root.update_idletasks()
        self.loading_done = False
        self.current_pair = name
        self._load_current_pair()
        self.loading_label.configure(text="")

    def _load_current_pair(self):
        # Configure Next/Prev buttons
        self.button_prev.config(state=tk.NORMAL)
        self.button_next.config(state=tk.NORMAL)
        if self.reverse_file_index[self.current_pair] == 0:
            self.button_prev.config(state=tk.DISABLED)
        if self.reverse_file_index[self.current_pair] + 1 == len(self.image_pairs):
            self.button_next.config(state=tk.DISABLED)

        # Load tags for pair
        self.tag_list.delete(0, tk.END)
        self.button_clear_all.config(state=tk.DISABLED)
        self.points = self.all_tags.get(self.current_pair, [])
        reset_canvases(canvas0=self.canvas0, canvas1=self.canvas1, points=self.points)
        for idx, (image_p0, image_p1) in enumerate(self.points):
            self.tag_list.insert(tk.END, format_tag(image_p0, image_p1, idx))

        if self.points:
            self.button_clear_all.config(state=tk.NORMAL)

        # Load images
        img0_path, img1_path = self.image_pairs[self.reverse_file_index[self.current_pair]]
        img0 = Image.open(img0_path)
        img1 = Image.open(img1_path)
        img0_name = os.path.basename(img0_path)
        img1_name = os.path.basename(img1_path)

        self.img0_label.configure(text=img0_name)
        self.img1_label.configure(text=img1_name)

        # Generate zoom pyramids
        self.canvas0.scaled_images = generate_image_pyramid(img0, IMG_SCALES)
        self.canvas1.scaled_images = generate_image_pyramid(img1, IMG_SCALES)

        # Put images on canvases
        put_image_on_canvas(self.canvas0, self.canvas0.scaled_images[self.canvas0.scale_idx])
        put_image_on_canvas(self.canvas1, self.canvas1.scaled_images[self.canvas1.scale_idx])

        # center images and reset zoom
        self.scale_to(self.canvas0, NEUTRAL_ZOOM_IDX)
        self.scale_to(self.canvas1, NEUTRAL_ZOOM_IDX)

        self.loading_done = True
        self.dropdown.set(self.current_pair)
        self.poll_cursor_position()

    def redraw_points(self, canvas: Canvas):
        # clear canvas first
        canvas.delete("point")

        for i, point in enumerate(canvas.points):
            if i == canvas.selected_tag_idx:
                outline = "#FFFFFF"
                pt_size = PT_BASE_SIZE + PT_SELECTED_EXTRA_SIZE + PT_ZOOM_SCALE_FACTOR * (
                            canvas.scale_idx + 1 - NEUTRAL_ZOOM_IDX)
            else:
                outline = "#000000"
                pt_size = PT_BASE_SIZE + PT_ZOOM_SCALE_FACTOR * (canvas.scale_idx + 1 - NEUTRAL_ZOOM_IDX)

            dim = 1 + pt_size * 2
            color = self.colors[i % MAX_COLORS]
            canvas_x, canvas_y = in_canvas_coords(point, canvas)
            x1, y1, x2, y2 = get_centered_oval_bbox((canvas_x, canvas_y), dim, dim, PT_OUTLINE_WIDTH)
            canvas.create_oval(x1, y1, x2, y2, width=PT_OUTLINE_WIDTH, fill=color, outline=outline, tags="point")

        if point := canvas.temp_point:
            pt_size = PT_BASE_SIZE + PT_ZOOM_SCALE_FACTOR * (canvas.scale_idx + 1 - NEUTRAL_ZOOM_IDX)
            dim = 1 + pt_size * 2
            canvas_x, canvas_y = in_canvas_coords(point, canvas)
            x1, y1, x2, y2 = get_centered_oval_bbox((canvas_x, canvas_y), dim, dim, PT_OUTLINE_WIDTH)
            canvas.create_oval(x1, y1, x2, y2, width=PT_OUTLINE_WIDTH,
                               fill="#000000", outline="#FFFFFF", tags="point")
            canvas.tag_text.configure(text=f"({point[0]:.1f}, {point[1]:.1f})", fg="black")

    def on_click(self, event):
        if not self.loading_done:
            return

        if event.widget == self.root:
            self.root.focus_set()

    def on_canvas_click(self, event):
        if not self.loading_done:
            return

        # If panning, (ctrl held)
        if not self.tag_mode:
            self.pan_start_x = event.x
            self.pan_start_y = event.y

        # If tagging
        else:
            click_canvas: Canvas = event.widget
            if click_canvas.temp_point:
                return  # ignore, this canvas already has a clicked point

            elif (img_point := in_image_coords(event.x, event.y, click_canvas)) != (-1, -1):

                if not click_canvas.twin.temp_point:
                    if (close_point_idx := find_closest(img_point, click_canvas.points, click_canvas.scale_idx)) != -1:
                        self.on_tag_selected_from_image(close_point_idx)
                        return
                    else:
                        self._clear_tag_select()

                    click_canvas.twin.tag_text.configure(text="")

                click_canvas.temp_point = img_point
                self.redraw_points(click_canvas)
            else:
                return  # ignore, clicked outside of image

    def confirm_tag(self, event):
        if (image_p0 := self.canvas0.temp_point) and (image_p1 := self.canvas1.temp_point):
            self.tag_list.insert(tk.END, format_tag(image_p0, image_p1, len(self.points)))
            self.button_clear_all.configure(state=tk.NORMAL)

            self.points.append((image_p0, image_p1))
            self.canvas0.points.append(image_p0)
            self.canvas1.points.append(image_p1)

            self.canvas0.temp_point = None
            self.canvas1.temp_point = None

            self.redraw_points(self.canvas0)
            self.redraw_points(self.canvas1)

            col_idx = (len(self.points) - 1) % MAX_COLORS
            color = self.colors[col_idx]

            self.canvas0.tag_text.configure(fg=color, bg="lightgrey" if col_idx == 2 else self.root_bg_color)
            self.canvas1.tag_text.configure(fg=color, bg="lightgrey" if col_idx == 2 else self.root_bg_color)

            self.all_tags[self.current_pair] = self.points

    def delete_tag(self, event):
        listbox: tk.Listbox = event.widget
        if selected_indices := listbox.curselection():
            # First delete all tags after (and including) selected
            listbox.delete(selected_indices[0], listbox.index(tk.END))

            # Remove selected from memory
            self.points.pop(selected_indices[0])
            self.canvas0.points.pop(selected_indices[0])
            self.canvas1.points.pop(selected_indices[0])

            # Add all other tags back (to maintain index order)
            for index, (p0, p1) in enumerate(self.points[selected_indices[0]:], start=selected_indices[0]):
                self.tag_list.insert(tk.END, format_tag(p0, p1, index))

            self._clear_tag_select()

        if not self.points:
            self.button_clear_all.configure(state=tk.DISABLED)

    def clear_all_tags(self):
        if self.points and messagebox.askyesno("Confirmation", "Are you sure?"):
            self.tag_list.delete(0, tk.END)
            self.points.clear()
            reset_canvases(canvas0=self.canvas0, canvas1=self.canvas1, points=[])
            self.redraw_points(self.canvas0)
            self.redraw_points(self.canvas1)

    def on_tag_selected_from_image(self, tag_idx: int):
        self.suppress_select_event = True

        self.tag_list.focus_set()
        self.tag_list.selection_clear(0, tk.END)
        self.tag_list.selection_set(tag_idx)
        self.tag_list.activate(tag_idx)
        self.tag_list.see(tag_idx)
        self._select_tag(tag_idx)

        self.suppress_select_event = False

    def on_tag_selected_from_list(self, event):
        if not self.loading_done or self.suppress_select_event:
            return

        if selected_index := event.widget.curselection():
            self._select_tag(selected_index[0])

    def _select_tag(self, selected_index):
        self.canvas0.selected_tag_idx = selected_index
        self.canvas1.selected_tag_idx = selected_index
        self.redraw_points(self.canvas0)
        self.redraw_points(self.canvas1)
        self.root.update_idletasks()

    def clear_tag_selection_inside(self, event):
        if not self.loading_done:
            return

        # Get the mouse coordinates within the Listbox
        listbox = event.widget
        x, y = event.x, event.y

        # Get the index of the item at the mouse position
        index = listbox.nearest(y)

        # Check if the click is within the bounds of the items
        if listbox.bbox(index):  # If the index has a valid bounding box
            item_x, item_y, item_w, item_h = listbox.bbox(index)
            if not (item_x <= x <= item_x + item_w and item_y <= y <= item_y + item_h):
                self._clear_tag_select()

        else:
            self._clear_tag_select()

    def _clear_tag_select(self):
        self.tag_list.selection_clear(0, tk.END)  # Clear selection
        self.canvas0.selected_tag_idx = None
        self.canvas1.selected_tag_idx = None
        self.root.focus_set()
        self.redraw_points(self.canvas0)
        self.redraw_points(self.canvas1)

    def undo_point(self, event):
        canvas: Canvas = event.widget  # Only triggers when clicking on a canvas...
        if canvas.temp_point:
            canvas.temp_point = None
            canvas.tag_text.configure(text="")
            self.redraw_points(canvas)

        else:
            self._clear_tag_select()

    def poll_cursor_position(self):
        if not self.loading_done:
            return

        # Get cursor position relative to the canvas
        inside = False
        cursor_x, cursor_y = self.root.winfo_pointerx(), self.root.winfo_pointery()

        # Check if the cursor is inside the first image
        if (canvas_pt := get_canvas_position(cursor_x, cursor_y, self.canvas0)) != (-1, -1):
            inside = True
            canvas_x, canvas_y = canvas_pt
            zoom_scale = self.canvas0.zoom_scale
            image_x, image_y = self.canvas0.coords("image")
            self.img0_cursor_txt.configure(text=f"{((canvas_x - image_x) / zoom_scale):.1f}, "
                                                f"{((canvas_y - image_y) / zoom_scale):.1f}")
            self.img1_cursor_txt.configure(text="")  # Clear text when outside
        # Check if the cursor is inside the second image
        elif (canvas_pt := get_canvas_position(cursor_x, cursor_y, self.canvas1)) != (-1, -1):
            inside = True
            canvas_x, canvas_y = canvas_pt
            zoom_scale = self.canvas1.zoom_scale
            image_x, image_y = self.canvas1.coords("image")
            self.img1_cursor_txt.configure(text=f"{((canvas_x - image_x) / zoom_scale):.1f}, "
                                                f"{((canvas_y - image_y) / zoom_scale):.1f}")
            self.img0_cursor_txt.configure(text="")  # Clear text when outside
        else:
            self.img0_cursor_txt.configure(text="")
            self.img1_cursor_txt.configure(text="")  # Clear text when outside

        # change cursor based on mode and position
        if inside:
            if self.tag_mode:
                self.root.configure(cursor="tcross")
            else:  # pan mode
                self.root.configure(cursor="fleur")
        else:
            self.root.configure(cursor="arrow")

        # Poll again after 100ms
        self._poll_scheduler_id = self.root.after(INTERVAL_POLL, self.poll_cursor_position)

    def mode_switch(self, event):
        if event.type == "2":  # KeyPress
            self.tag_mode = False
        elif event.type == "3":  # KeyRelease
            self.tag_mode = True

    def pan_image(self, event):
        if not self.tag_mode:
            # Calculate the distance moved
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y

            # Adjust the view of the canvas
            event.widget.move("image", dx, dy)

            # Update the starting point
            self.pan_start_x = event.x
            self.pan_start_y = event.y

            # Keep the points in their places
            self.redraw_points(self.canvas0)
            self.redraw_points(self.canvas1)

    def zoom(self, event):
        # Event triggered by windows scrolling
        if self.loading_done:
            if event.delta > 0:
                self.scale_up(event)
            else:
                self.scale_down(event)

    def scale_up(self, event):
        canvas: Canvas = event.widget
        if self.loading_done and canvas.scale_idx + 1 < len(IMG_SCALES):
            event_point = event.x, event.y
            canvas.scale_idx += 1
            apply_image_scaling(canvas, event_point)
            self.redraw_points(canvas)

    def scale_down(self, event):
        canvas: Canvas = event.widget
        if self.loading_done and canvas.scale_idx > 0:
            event_point = event.x, event.y
            canvas.scale_idx -= 1
            apply_image_scaling(canvas, event_point)
            self.redraw_points(canvas)

    def scale_to(self, canvas: Canvas, idx: int):
        if not 0 <= idx < len(IMG_SCALES):
            raise IndexError

        canvas.scale_idx = idx
        apply_image_scaling(canvas, (0, 0))
        self.redraw_points(canvas)

    def on_focus_out(self, event):
        # Any held keys should be treated as released!
        self.tag_mode = True

    def prev_pair(self):
        if not self.loading_done:
            return

        curr_idx = self.reverse_file_index[self.current_pair]
        if curr_idx > 0:
            name = self.file_index[curr_idx - 1]
            self.load_selected_pair(name=name)

    def next_pair(self):
        if not self.loading_done:
            return

        curr_idx = self.reverse_file_index[self.current_pair]
        if curr_idx < len(self.file_index) - 1:
            name = self.file_index[curr_idx + 1]
            self.load_selected_pair(name=name)

    def save_tags(self):
        if self.current_pair is not None and self.loading_done:
            name = get_tag_name_convention(self.data_dir)
            tags_path = os.path.join(self.data_dir, name)
            payload = {"open_pair_name": self.current_pair,
                       "timestamp": "",
                       "all_tags": self.all_tags}

            with open(tags_path, "w") as f:
                json.dump(payload, f)

        self._save_scheduler_id = self.root.after(INTERVAL_SAVE, self.save_tags)

    def quit_event(self, event):
        if self.debug:
            self.root.quit()
        else:
            if messagebox.askyesno("Confirmation", "Exit?"):
                self.root.quit()
