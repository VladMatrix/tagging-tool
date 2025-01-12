from __future__ import annotations
import colorsys
import os.path
import tkinter as tk
from collections import Counter
from PIL import Image, ImageTk, ImageFile
import json
from constants import IMG_SCALES, IMG_FILES, PT_ZOOM_SCALE_FACTOR


class Canvas(tk.Canvas):
	def __init__(self, *args, **kwargs):
		tk.Canvas.__init__(self, *args, **kwargs)
		self.points = []
		self.image = None
		self.temp_point = None
		self.tag_text = None
		self.twin = None
		self.selected_tag_idx = None
		self.zoom_scale = 1  # IMG_SCALES[self.scale_idx]
		self.scale_idx = IMG_SCALES.index(self.zoom_scale)
		self.scaled_images = None


def get_tag_name_convention(path: str) -> str:
	return f"tags_{os.path.split(path)[-1]}_.json"


def read_tags_file(path: str) -> tuple[bool, dict | str]:
	if os.path.isfile(path):
		with open(path, "r") as f:
			payload = json.load(f)

		if "all_tags" in payload:
			return True, payload
		else:
			return False, "File opened but it has no tags"

	else:
		return True, {}


def make_pairs(file_names: list[str]) -> tuple[bool, str | list[tuple[str, str]]]:
	if not len(file_names):
		return False, f"No images found!\nSelect a folder with images {IMG_FILES}."

	if len(file_names) % 2 != 0:
		return False, "Please select a directory with an even number of images (pairs)."

	# remove ext, suffix
	files_no_ext = list(map(lambda x: os.path.splitext(x)[0], file_names))
	correctly_numbered = list(filter(lambda x: x.endswith(("_1", "_2")), files_no_ext))

	if len(correctly_numbered) != len(files_no_ext):
		return False, "incorrectly formatted names"

	counts_no_suffix = Counter(list(map(lambda x: x[:-2], correctly_numbered)))
	for name, count in counts_no_suffix.items():
		if count != 2:
			return False, "some image no pair"

	sorted_names = sorted(file_names)
	return True, [(sorted_names[i], sorted_names[i + 1]) for i in range(0, len(sorted_names), 2)]


def generate_rainbow_colors(n_points: int) -> list[str]:
	# Define the start and end hues in the HSV color space
	start_hue = 0.0  # Red (0 degrees in HSV)
	end_hue = 5 / 6  # Magenta (300 degrees in HSV, scaled to 0-1)

	# Generate evenly spaced hues
	hues = [start_hue + (end_hue - start_hue) * i / (n_points - 1) for i in range(n_points)]

	# Convert HSV to RGB and then to 0xRRGGBB format
	hex_colors = []
	for hue in hues:
		r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)  # Saturation and Value are both 1 for full colors
		hex_colors.append(f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}")

	return hex_colors


def generate_image_pyramid(image: Image, scales: tuple[float, ...]) -> tuple[ImageTk.PhotoImage, ...]:
	pyramid = []
	for scale in scales:  # TODO might be worth doing with cv2?
		# Calculate the new size
		new_width = int(image.width * scale)
		new_height = int(image.height * scale)

		# Resize the image and append to the pyramid
		resized_image = image.resize((new_width, new_height), Image.Resampling.BILINEAR)
		pyramid.append(ImageTk.PhotoImage(resized_image))

	return tuple(pyramid)


def put_image_on_canvas(canvas: Canvas, image: ImageFile, coords: tuple[float, float] = (0, 0)):
	""" Place the given PIL image on the given canvas at the given coordinates. """
	canvas.delete("image")
	x, y = coords
	canvas.image = image
	canvas.create_image(x, y, anchor=tk.NW, image=canvas.image, tags="image")
	canvas.config(scrollregion=(0, 0, canvas.image.width(), canvas.image.height()))


def get_canvas_position(cursor_x: int | float, cursor_y: int | float, canvas) -> tuple[int, int]:
	""" Returns the position of the cursor on the canvas, if inside. Otherwise, returns (-1, -1). """
	canvas_x, canvas_y = canvas.winfo_rootx(), canvas.winfo_rooty()
	canvas_width, canvas_height = canvas.winfo_width(), canvas.winfo_height()
	if canvas_x <= cursor_x <= canvas_x + canvas_width and canvas_y <= cursor_y <= canvas_y + canvas_height:
		# Map cursor to canvas coordinates
		canvas_cursor_x = canvas.canvasx(cursor_x - canvas_x)
		canvas_cursor_y = canvas.canvasy(cursor_y - canvas_y)
	else:
		canvas_cursor_x = -1
		canvas_cursor_y = -1
	return canvas_cursor_x, canvas_cursor_y


def apply_image_scaling(canvas: Canvas, event_point: tuple[float, float]):
	canvas.zoom_scale = IMG_SCALES[canvas.scale_idx]
	old_x, old_y = canvas.coords("image")
	new_image = canvas.scaled_images[canvas.scale_idx]
	new_w, new_h = new_image.width(), new_image.height()
	event_x, event_y = event_point

	# Get all relevant parameters
	old_w, old_h = canvas.image.width(), canvas.image.height()
	old_cx, old_cy = old_w / 2, old_h / 2
	ratio_w = new_w / old_w
	ratio_h = new_h / old_h
	canvas_mouse_x = canvas.canvasx(event_x)
	canvas_mouse_y = canvas.canvasy(event_y)

	# Get delta in "top left" due to centering at the same center
	center_dx = (old_w - new_w) / 2
	center_dy = (old_h - new_h) / 2

	# Get delta considering mouse position relative to image centers
	img_mouse_x = canvas_mouse_x - old_x
	img_mouse_y = canvas_mouse_y - old_y
	mouse_dx = (old_cx - img_mouse_x) * (1 - ratio_w)
	mouse_dy = (old_cy - img_mouse_y) * (1 - ratio_h)

	# Calculate final deltas and new point
	dx = center_dx - mouse_dx
	dy = center_dy - mouse_dy
	new_x = old_x + dx
	new_y = old_y + dy

	put_image_on_canvas(canvas, new_image, (new_x, new_y))


def reset_canvases(*, canvas0: Canvas, canvas1: Canvas, points: list[tuple[tuple[int, int], tuple[int, int]]]) -> None:
	canvas0.points = []
	canvas1.points = []
	canvas0.temp_point = None
	canvas1.temp_point = None
	for p0, p1 in points:
		canvas0.points.append(p0)
		canvas1.points.append(p1)

	canvas0.tag_text.configure(text="", bg=canvas0.master.cget("bg"))
	canvas1.tag_text.configure(text="", bg=canvas1.master.cget("bg"))


def in_canvas_coords(point: tuple[int | float, int | float], canvas: Canvas) -> tuple[float, float]:
	""" Return the given image point in its canvas' coordinates. """
	x, y = point
	img_tl_x, img_tl_y = canvas.coords("image")
	return (x * canvas.zoom_scale + img_tl_x), (y * canvas.zoom_scale + img_tl_y)


def in_image_coords(x: int | float, y: int | float, canvas: Canvas) -> tuple[float, float]:
	""" Return the given canvas point normalized to image coordinates, if inside the image. Else returns (-1, -1). """
	img_tl_x, img_tl_y = canvas.coords("image")
	w, h = canvas.image.width(), canvas.image.height()
	x -= img_tl_x
	y -= img_tl_y

	if 0 <= x < w and 0 <= y < h:
		return x / canvas.zoom_scale, y / canvas.zoom_scale
	else:
		return -1, -1


def format_tag(point0: tuple[float, float], point1: tuple[float, float], idx: int) -> str:
	x0, y0 = point0
	x1, y1 = point1
	string = f"{idx + 1}. [{round(x0)}, {round(y0)}] - [{round(x1)}, {round(y1)}]"
	return string


def find_closest(click_point: tuple[float, float], points: list[tuple[float, float]], zoom_idx: int) -> int:
	thresh = max(3., 10 - 1.5 * zoom_idx)
	min_dist = 1e12
	min_dist_idx = -1
	x0, y0 = click_point
	for idx, (x1, y1) in enumerate(points):
		dist = ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
		if dist <= thresh and dist < min_dist:
			min_dist_idx = idx
			min_dist = dist

	# print(min_dist)
	return min_dist_idx
