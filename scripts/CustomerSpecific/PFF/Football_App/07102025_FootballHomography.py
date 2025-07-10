import os
# Ensure HOME is set for Clarifai client on Windows
if "HOME" not in os.environ and "USERPROFILE" in os.environ:
    os.environ["HOME"] = os.environ["USERPROFILE"]

import cv2
import numpy as np
import tkinter as tk
from tkinter import Canvas, Button, Frame, Scale, Label, filedialog, IntVar, HORIZONTAL, Spinbox, messagebox, simpledialog, StringVar
from PIL import Image, ImageTk
from clarifai.client.model import Model
import os
import time
import tempfile

# Basic imports
import torch
import torchvision.transforms as T
from scipy.optimize import linear_sum_assignment

# Import segment_anything
from segment_anything import sam_model_registry, SamPredictor

class FootballHomographyApp:
    def __init__(self, root, video_path, clarifai_pat, field_width=100, field_height=60):
        self.root = root
        self.root.title("Football Homography Mapping")
        
        # Parameters
        self.video_path = video_path
        self.field_width = field_width  # Yards (standard American football field)
        self.field_height = field_height  # Yards
        self.conf_threshold = 0.5  # Default confidence threshold
        self.min_keypoints = 4  # Minimum number of keypoints required
        self.max_keypoints = 50  # Maximum number of keypoints allowed
        self.num_keypoints = 4  # Default number of keypoints to use
        
        # Clarifai PAT and model URLs
        self.clarifai_pat = clarifai_pat
        self.model_url_player_ref = "https://clarifai.com/pff-org/labelstudio-player-ref/models/player-ref-yolo"
        self.model_url_yard = "https://clarifai.com/pff-org/labelstudio-yard/models/hash-yard-cv-4-agnostic"
        self.model_player_ref = Model(url=self.model_url_player_ref, pat=self.clarifai_pat)
        self.model_yard = Model(url=self.model_url_yard, pat=self.clarifai_pat)
        self.concepts_player_ref = ["players", "referee"]
        self.concepts_yard = [
            "10", "20", "30", "40", "50", "goal_line", "inner", "low_edge", "up_edge"
        ]
        # Default detection mode: 'player_ref' or 'yard'
        self.detection_mode = 'player_ref'
        
        # Initialize segmentation model
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Initializing segmentation model on {device}")
        
        try:
            checkpoint_path = "models/sam_vit_h.pth"
            if not os.path.exists(checkpoint_path):
                messagebox.showerror("Error", f"Checkpoint not found at {checkpoint_path}")
                raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
                
            # Initialize using segment_anything
            self.sam = sam_model_registry["vit_h"](checkpoint=checkpoint_path)
            self.sam.to(device=device)
            self.sam_predictor = SamPredictor(self.sam)
            print("Original SAM initialized successfully!")
            
            # Set flag to indicate if segmentation is available
            self.segmentation_available = True
            
        except Exception as e:
            print(f"Error initializing segmentation model: {e}")
            import traceback
            traceback.print_exc()
            self.sam = None
            self.sam_predictor = None
            self.segmentation_available = False
            messagebox.showerror("Error", f"Failed to initialize segmentation model: {e}")
        
        # Initialize tracking variables
        self.prev_masks = None
        self.prev_boxes = None
        self.prev_track_ids = None
        
        # Track state
        self.tracks = []  # List to store active tracks
        self.track_colors = {}  # Dictionary to store consistent colors for tracks
        
        # Extract first frame from video
        self.cap = cv2.VideoCapture(video_path)
        ret, self.frame = self.cap.read()
        if not ret:
            raise Exception("Failed to read video file")
        
        self.original_frame = self.frame.copy()
        self.height, self.width = self.frame.shape[:2]
        
        # Load the topdown field image
        self.field_img = self.load_field_image('clean_football_field.jpg') #NFL-field-hash-marks.jpg')  #topdown_graphic.webp')
        
        # Setup UI
        self.setup_ui()
        
        # Variables for homography
        self.source_points = []
        self.destination_points = []
        self.homography_matrix = None
        self.player_positions = []
        
        # Selection state
        self.selecting_source = True
        self.source_complete = False
        self.dest_complete = False
        
        # Last detected image
        self.last_field_with_players = None
        
        # Add variables for camera motion tracking
        self.prev_frame = None
        self.prev_keypoints = None
        self.prev_descriptors = None
        self.feature_detector = cv2.SIFT_create()
        self.feature_matcher = cv2.BFMatcher_create(cv2.NORM_L2, crossCheck=True)
        
        # Enhanced tracking variables
        self.motion_history = []  # Store recent motion matrices
        self.motion_history_size = 10  # Number of motion matrices to keep for smoothing
        self.motion_predictions = None  # For Kalman filter predictions
        self.use_kalman_filter = True  # Enable/disable Kalman filtering
        self.adaptive_ransac_threshold = 4.0  # Starting RANSAC threshold (pixels)
        self.max_ransac_threshold = 10.0  # Max RANSAC threshold for fast movements
        self.min_ransac_threshold = 1.0  # Min RANSAC threshold for slow movements
        self.optical_flow_params = dict(
            winSize=(10, 10),  # Larger window for faster movements
            maxLevel=5,        # More pyramid levels for large motions
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 0.01), # 30 iterations with 0.01 pixel accuracy
            flags=cv2.OPTFLOW_FARNEBACK_GAUSSIAN  # More robust optical flow
        )
        
        # Add variables for player tracking
        self.player_tracks = {}  # Dictionary to store player tracks: {player_id: [(x1,y1), (x2,y2), ...]}
        self.player_colors = {}  # Dictionary to store consistent colors for players
        self.next_player_id = 1
        self.track_history_length = 5000  # Number of frames to keep in track history
        self.max_tracking_distance = 10  # Maximum distance to consider for the same player
        
        # Add temporal smoothing variables
        self.frame_count = 0  # Current frame counter
        self.last_processed_frame = 0  # Last frame that was processed
        self.interpolated_positions = {}  # Store interpolated positions for smooth tracking
        self.smoothing_window = 3  # Reduced from 5 - less aggressive smoothing
        self.position_smoothing_factor = 0.3  # Reduced from 0.7 - much less aggressive smoothing
        self.velocity_smoothing_factor = 0.5  # Reduced from 0.8 - less aggressive velocity smoothing
        self.interpolation_frames = 2  # Reduced from 3 - less interpolation
        
        # Initialize color palette for players
        self.color_palette = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (128, 0, 0),    # Maroon
            (0, 128, 0),    # Dark Green
            (0, 0, 128),    # Navy
            (128, 128, 0),  # Olive
            (128, 0, 128),  # Purple
            (0, 128, 128),  # Teal
            (192, 192, 0),  # Light Yellow
            (192, 0, 192),  # Light Magenta
            (0, 192, 192),  # Light Cyan
        ]

        # Add motion smoothing parameters
        self.motion_history_size = 10  # Number of frames to keep for smoothing
        self.position_history = {}  # Store recent positions for each player
        self.position_history_size = 60  # Number of positions to keep for each player
        self.smoothing_factor = 0.2  # Reduced from 0.5 - much less aggressive smoothing
        self.max_jump_distance = 10  # Maximum allowed distance between consecutive positions
        self.velocity_history = {}  # Store velocity for each player
        self.velocity_history_size = 10  # Number of velocity measurements to keep

        # Add variables for 5-yard segment
        self.reference_points = []  # Store the two points for 5-yard segment
        self.reference_complete = False
        self.pixels_per_yard = None  # Store the conversion factor

        # Add field of view tracking variables
        self.field_of_view_points = []  # Store points that define the field of view boundary
        self.field_of_view_history = []  # Store recent field of view boundaries for smoothing
        self.max_fov_history = 5  # Number of field of view boundaries to keep for smoothing

        # Constants for dynamic keypoint management
        self.MIN_TRACKING_POINTS = 200  # Reduced from 300 for more stable tracking
        self.MAX_TRACKING_POINTS = 1000  # Reduced from 1000 to avoid tracking too many points
        self.player_mask = None # Initialize player mask

    def load_field_image(self, image_path):
        """Load the field image from a file path"""
        try:
            # Try to read the image file
            field_img = cv2.imread(image_path, cv2.IMREAD_COLOR)
            
            # If loading failed, try with PIL which can handle more formats
            if field_img is None:
                pil_image = Image.open(image_path)
                field_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # Resize if needed to match our expected dimensions
            field_height, field_width = field_img.shape[:2]
            if field_height != self.field_height*10 or field_width != self.field_width*10:
                field_img = cv2.resize(field_img, (self.field_width*10, self.field_height*10))
            
            return field_img
        except Exception as e:
            print(f"Error loading field image: {e}")
            # Fall back to the programmatically created field
            return self.create_field_image()

    def create_field_image(self):
        # Create a simple green field with yard lines
        field_img = np.ones((self.field_height*10, self.field_width*10, 3), dtype=np.uint8) * 76  # Dark green
        field_img[:, :, 0] = 0  # B = 0
        field_img[:, :, 1] = 180  # G = 180
        field_img[:, :, 2] = 0  # R = 0
        
        # Draw yard lines (every 10 yards)
        for i in range(0, self.field_width+1, 10):
            x = i * 10
            cv2.line(field_img, (x, 0), (x, self.field_height*10), (255, 255, 255), 2)
        
        # Draw yard lines across the field
        for i in range(0, self.field_height+1, 10):
            y = i * 10
            cv2.line(field_img, (0, y), (self.field_width*10, y), (255, 255, 255), 2)
            
        return field_img

    def setup_ui(self):
        main_frame = Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Original image canvas
        img_frame = Frame(main_frame)
        img_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Convert frame to RGB for tkinter
        rgb_frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        img = img.resize((int(self.width * 0.8), int(self.height * 0.8)))
        self.tk_img = ImageTk.PhotoImage(image=img)
        
        self.canvas = Canvas(img_frame, width=img.width, height=img.height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_img = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        
        # Field view canvas
        field_frame = Frame(main_frame)
        field_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        field_img_rgb = cv2.cvtColor(self.field_img, cv2.COLOR_BGR2RGB)
        field_pil = Image.fromarray(field_img_rgb)
        self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
        
        self.field_canvas = Canvas(field_frame, width=field_pil.width, height=field_pil.height)
        self.field_canvas.pack(fill=tk.BOTH, expand=True)
        self.field_canvas_img = self.field_canvas.create_image(0, 0, anchor=tk.NW, image=self.field_tk_img)
        self.field_canvas.bind("<Button-1>", self.on_field_click)
        
        # Controls frame
        controls_frame = Frame(self.root)
        controls_frame.pack(fill=tk.X, pady=5)
        
        # Confidence threshold slider
        conf_frame = Frame(controls_frame)
        conf_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        Label(conf_frame, text="Confidence Threshold:").pack(side=tk.LEFT, padx=5)
        
        self.conf_slider = Scale(conf_frame, from_=0.1, to=1.0, resolution=0.05, 
                                orient=HORIZONTAL, length=200, command=self.update_conf)
        self.conf_slider.set(self.conf_threshold)
        self.conf_slider.pack(side=tk.LEFT, padx=5)
        
        # Skip frames control for video processing
        skip_frame_frame = Frame(controls_frame)
        skip_frame_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        Label(skip_frame_frame, text="Process every N frames:").pack(side=tk.LEFT, padx=5)
        
        self.skip_frames_var = IntVar()
        self.skip_frames_var.set(1)  # Default to processing all frames
        
        self.skip_frames_spinbox = Spinbox(skip_frame_frame, from_=1, to=30, 
                                     width=5, textvariable=self.skip_frames_var)
        self.skip_frames_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Instructions and buttons
        btn_frame = Frame(self.root)
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.instruction_label = tk.Label(btn_frame, text="Select points on the football field (minimum 4)")
        self.instruction_label.pack(side=tk.TOP, pady=5)
        
        # Main action buttons
        self.preview_btn = Button(btn_frame, text="Preview Detections", command=self.preview_detections)
        self.preview_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = Button(btn_frame, text="Reset Points", command=self.reset_points)
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        self.switch_btn = Button(btn_frame, text="Switch to Field Selection", command=self.switch_selection_mode, state=tk.DISABLED)
        self.switch_btn.pack(side=tk.LEFT, padx=5)

        self.detect_btn = Button(btn_frame, text="Detect Players", command=self.detect_players, state=tk.DISABLED)
        self.detect_btn.pack(side=tk.LEFT, padx=5)
        
        
        self.save_btn = Button(btn_frame, text="Save Bird's Eye View", command=self.save_field_image, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
                # Add reference segment button after the switch button
        self.reference_btn = Button(btn_frame, text="Select 5-Yard Segment", 
                                  command=self.start_reference_selection, state=tk.DISABLED)
        self.reference_btn.pack(side=tk.LEFT, padx=5)

        # Add process video button
        self.process_video_btn = Button(btn_frame, text="Process Video", command=self.start_video_processing, state=tk.DISABLED)
        self.process_video_btn.pack(side=tk.LEFT, padx=5)
        
        self.debug_btn = Button(btn_frame, text="Debug Info", command=self.show_debug_info)
        self.debug_btn.pack(side=tk.LEFT, padx=5)
        
        # Add detection mode selection
        mode_frame = Frame(controls_frame)
        mode_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        Label(mode_frame, text="Detection Mode:").pack(side=tk.LEFT, padx=5)
        self.mode_var = StringVar()
        self.mode_var.set('player_ref')
        tk.Radiobutton(mode_frame, text="Player/Referee", variable=self.mode_var, value='player_ref', command=self.update_detection_mode).pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="Yard Markers", variable=self.mode_var, value='yard', command=self.update_detection_mode).pack(side=tk.LEFT)

    def update_keypoints(self):
        """Update the number of keypoints to use"""
        try:
            value = int(self.keypoints_var.get())
            print(f"Keypoint value from control: {value}")
            
            if self.min_keypoints <= value <= self.max_keypoints:
                old_value = self.num_keypoints
                self.num_keypoints = value
                self.instruction_label.config(text=f"Select {self.num_keypoints} points on the football field")
                
                # Reset points if changing the number of keypoints
                if len(self.source_points) > 0 or len(self.destination_points) > 0:
                    self.reset_points()
                
                print(f"Updated number of keypoints from {old_value} to {self.num_keypoints}")
                
            else:
                print(f"Invalid keypoint value: {value} (must be between {self.min_keypoints} and {self.max_keypoints})")
                # Reset to previous valid value
                self.keypoints_var.set(str(self.num_keypoints))
        except ValueError as e:
            print(f"Error updating keypoints: {e}")
            # If not a valid number, reset to default
            self.keypoints_var.set(str(self.num_keypoints))
            messagebox.showerror("Invalid Value", f"Please enter a number between {self.min_keypoints} and {self.max_keypoints}")
            
        # Print the current state to help debug
        print(f"Current keypoint state: self.num_keypoints={self.num_keypoints}, spinbox value={self.keypoints_var.get()}")

    def update_conf(self, val):
        self.conf_threshold = float(val)
        print(f"Updated confidence threshold to {self.conf_threshold}")
        
    def update_detection_mode(self):
        self.detection_mode = self.mode_var.get()
        print(f"Detection mode set to {self.detection_mode}")
        self.instruction_label.config(text=f"Detection mode: {self.detection_mode}")

    def preview_detections(self):
        _, img_encoded = cv2.imencode('.jpg', self.original_frame)
        img_bytes = img_encoded.tobytes()
        try:
            if self.detection_mode == 'player_ref':
                results = self.model_player_ref.predict_by_bytes(img_bytes, input_type="image")
                concepts = self.concepts_player_ref
            else:
                results = self.model_yard.predict_by_bytes(img_bytes, input_type="image")
                concepts = self.concepts_yard
            regions = results.outputs[0].data.regions
            pred_frame = self.original_frame.copy()
            field_with_players = self.field_img.copy()
            detection_count = 0
            for region in regions:
                # Only process regions matching selected concepts
                if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                    region_concepts = [c.name for c in region.data.concepts]
                    if not any(concept in region_concepts for concept in concepts):
                        continue
                bbox = region.region_info.bounding_box
                x1 = int(bbox.left_col * self.width)
                y1 = int(bbox.top_row * self.height)
                x2 = int(bbox.right_col * self.width)
                y2 = int(bbox.bottom_row * self.height)
                # Get confidence ONLY from first concept
                conf = 0.0
                if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                    concepts_list = region.data.concepts
                    if concepts_list and hasattr(concepts_list[0], 'value'):
                        conf = concepts_list[0].value
                
                # Get the concept name for labeling
                concept_name = "unknown"
                if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                    concepts_list = region.data.concepts
                    if concepts_list and hasattr(concepts_list[0], 'name'):
                        concept_name = concepts_list[0].name
                
                # Different visualization for yard markers vs players
                if self.detection_mode == 'yard':
                    # Yard marker visualization - use different colors and shapes
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    
                    # Use different colors for different types of yard markers
                    if concept_name in ["10", "20", "30", "40", "50"]:
                        color = (255, 0, 255)  # Magenta for yard numbers
                        shape = "rectangle"
                    elif concept_name in ["goal_line"]:
                        color = (0, 255, 255)  # Yellow for goal line
                        shape = "rectangle"
                    elif concept_name in ["inner", "low_edge", "up_edge"]:
                        color = (255, 255, 0)  # Cyan for hash marks
                        shape = "diamond"
                    else:
                        color = (128, 128, 128)  # Gray for unknown
                        shape = "rectangle"
                    
                    # Draw shape based on type
                    if shape == "rectangle":
                        cv2.rectangle(pred_frame, (x1, y1), (x2, y2), color, 2)
                    elif shape == "diamond":
                        # Draw diamond shape with thicker lines
                        points = np.array([
                            [center_x, y1],
                            [x2, center_y],
                            [center_x, y2],
                            [x1, center_y]
                        ], np.int32)
                        cv2.polylines(pred_frame, [points], True, color, 3)
                    
                    # Add label with concept name
                    label_text = f"{concept_name} ({conf:.2f})"
                    cv2.putText(pred_frame, label_text, (x1, y1 - 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                else:
                    # Player/referee visualization (original style)
                    foot_x = int((x1 + x2) / 2)
                    foot_y = int(y2)
                    cv2.rectangle(pred_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.circle(pred_frame, (foot_x, foot_y), 5, (0, 0, 255), -1)
                    conf_text = f"{concept_name} ({conf:.2f})"
                    cv2.putText(pred_frame, conf_text, (x1, y1 - 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                detection_count += 1
            pred_frame_rgb = cv2.cvtColor(pred_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(pred_frame_rgb)
            img = img.resize((int(self.width * 0.8), int(self.height * 0.8)))
            self.tk_img = ImageTk.PhotoImage(image=img)
            self.canvas.itemconfig(self.canvas_img, image=self.tk_img)
            field_img_rgb = cv2.cvtColor(self.field_img, cv2.COLOR_BGR2RGB)
            field_pil = Image.fromarray(field_img_rgb)
            self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
            self.field_canvas.itemconfig(self.field_canvas_img, image=self.field_tk_img)
            print(f"Preview: Detected {detection_count} objects")
        except Exception as e:
            print(f"Error in preview_detections: {str(e)}")
            self.instruction_label.config(text=f"Error in preview: {str(e)}")

    def on_canvas_click(self, event):
        if not self.selecting_source or self.source_complete:
            return
            
        # Get click coordinates and scale them to original image size
        x = event.x
        y = event.y
        x_scaled = int(x / 0.8)
        y_scaled = int(y / 0.8)
        
        # Store the original (unscaled) coordinates for homography
        self.source_points.append((x_scaled, y_scaled))
        
        # Draw point on canvas using display coordinates
        point_id = len(self.source_points)
        point_radius = 5
        self.canvas.create_oval(
            x - point_radius, y - point_radius,
            x + point_radius, y + point_radius,
            fill="red", outline="white", tags=f"point_{point_id}"
        )
        self.canvas.create_text(
            x + 10, y - 10,
            text=str(point_id),
            fill="red",
            font=("Arial", 12, "bold"),
            tags=f"text_{point_id}"
        )
        
        # Draw lines connecting the points as they are added
        if len(self.source_points) > 1:
            # Get previous point coordinates and scale for display
            prev_x, prev_y = self.source_points[-2]
            prev_x_display = int(prev_x * 0.8)
            prev_y_display = int(prev_y * 0.8)
            
            # Draw line using display coordinates
            self.canvas.create_line(
                prev_x_display, prev_y_display,
                x, y,
                fill="red",
                width=2,
                tags=f"line_{point_id}"
            )
        
        # Update instruction label with current count
        self.instruction_label.config(text=f"Selected {len(self.source_points)} points on video frame. Click 'Switch to Field Selection' when done.")
        
        # Enable switch button after at least 4 points
        if len(self.source_points) >= 4:
            self.switch_btn.config(state=tk.NORMAL)

    def on_field_click(self, event):
        if self.selecting_source or self.dest_complete:
            return
            
        # Get click coordinates
        x, y = event.x, event.y
        
        # Only allow as many points as were selected in the source frame
        if len(self.destination_points) >= len(self.source_points):
            return
            
        # Add point to destination points
        self.destination_points.append((x, y))
        
        # Draw point on canvas
        point_id = len(self.destination_points)
        self.field_canvas.create_oval(x-5, y-5, x+5, y+5, fill="blue", outline="white")
        self.field_canvas.create_text(x+10, y-10, text=str(point_id), fill="blue", font=("Arial", 12, "bold"))
        
        # Draw lines connecting the points as they are added
        if len(self.destination_points) > 1:
            # Connect the new point with the previous one
            prev_idx = len(self.destination_points) - 2
            x1, y1 = self.destination_points[prev_idx]
            x2, y2 = self.destination_points[-1]
            self.field_canvas.create_line(x1, y1, x2, y2, fill="blue", width=2)
        
        # Update instruction label with remaining points
        remaining_points = len(self.source_points) - len(self.destination_points)
        if remaining_points > 0:
            self.instruction_label.config(text=f"Select {remaining_points} more points on the field")
        
        # If we have matched all source points
        if len(self.destination_points) == len(self.source_points):
            # Connect the last point with the first one to complete the shape
            x1, y1 = self.destination_points[-1]
            x2, y2 = self.destination_points[0]
            self.field_canvas.create_line(x1, y1, x2, y2, fill="blue", width=2)
            
            self.dest_complete = True
            self.compute_homography()
            self.detect_btn.config(state=tk.NORMAL)
            self.instruction_label.config(text="Homography computed. Click 'Detect Players'")

    def switch_selection_mode(self):
        if len(self.source_points) < 4:
            messagebox.showwarning("Warning", "Please select at least 4 points before switching to field selection.")
            return
            
        self.selecting_source = False
        self.switch_btn.config(state=tk.DISABLED)
        self.instruction_label.config(text=f"Now select {len(self.source_points)} corresponding points on the field")

    def reset_points(self):
        # Reset all points and state
        self.source_points = []
        self.destination_points = []
        self.player_positions = []
        self.homography_matrix = None
        self.last_field_with_players = None
        
        self.source_complete = False
        self.dest_complete = False
        self.selecting_source = True
        
        # Reset canvas
        self.canvas.delete("all")
        self.field_canvas.delete("all")
        
        # Redraw images with proper references
        rgb_frame = cv2.cvtColor(self.original_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        img = img.resize((int(self.width * 0.8), int(self.height * 0.8)))
        self.tk_img = ImageTk.PhotoImage(image=img)  # Keep reference
        self.canvas_img = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        
        field_img_rgb = cv2.cvtColor(self.field_img, cv2.COLOR_BGR2RGB)
        field_pil = Image.fromarray(field_img_rgb)
        self.field_tk_img = ImageTk.PhotoImage(image=field_pil)  # Keep reference
        self.field_canvas_img = self.field_canvas.create_image(0, 0, anchor=tk.NW, image=self.field_tk_img)
        
        # Reset buttons
        self.switch_btn.config(state=tk.DISABLED)
        self.detect_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        
        self.instruction_label.config(text=f"Select {self.num_keypoints} points on the football field")

    def compute_homography(self):
        if len(self.source_points) == len(self.destination_points) and len(self.source_points) >= self.min_keypoints:
            try:
                # Convert points to numpy arrays with proper dtype
                src_pts = np.array(self.source_points, dtype=np.float32)
                dst_pts = np.array(self.destination_points, dtype=np.float32)
                
                print(f"Computing homography with {len(src_pts)} points")
                print(f"Source points: {src_pts}")
                print(f"Destination points: {dst_pts}")
                
                # When more than 4 points are provided, use RANSAC method for better robustness
                method = cv2.RANSAC if len(self.source_points) > 4 else 0
                
                # Compute homography with proper parameters
                self.homography_matrix, mask = cv2.findHomography(
                    src_pts,   # These are the points on the video
                    dst_pts,  # These are the points on the field
                    method=method,  # Use RANSAC if more than 4 points
                    ransacReprojThreshold=5.0,  # Maximum reprojection error for inliers
                    maxIters=2000,  # Maximum iterations for RANSAC
                    confidence=0.998  # Confidence level for RANSAC
                )
                
                # Check if homography matrix is valid
                if self.homography_matrix is None or np.isnan(self.homography_matrix).any():
                    print("Error: Invalid homography matrix computed!")
                    self.instruction_label.config(text="Error: Invalid homography matrix. Try different points.")
                    return False
                
                if mask is not None:
                    inliers = np.sum(mask)
                    print(f"Homography computed with {inliers} inliers out of {len(src_pts)} points")
                    
                    # If using RANSAC and less than 70% of points are inliers, warn the user
                    if method == cv2.RANSAC and inliers < 0.7 * len(src_pts):
                        print(f"Warning: Only {inliers}/{len(src_pts)} points are inliers. Consider resetting and trying again.")
                        self.instruction_label.config(text=f"Warning: Only {inliers}/{len(src_pts)} points are good. Consider trying again.")
                
                print("Homography matrix computed:", self.homography_matrix)
                
                # Validate the homography matrix by testing all corners and center
                test_points = [
                    (0, 0),                          # top-left
                    (self.width-1, 0),               # top-right
                    (0, self.height-1),              # bottom-left
                    (self.width-1, self.height-1),   # bottom-right
                    (self.width//2, self.height//2)  # center
                ]
                
                valid_count = 0
                for x, y in test_points:
                    try:
                        test_point = np.array([[[x, y]]], dtype=np.float32)
                        test_result = cv2.perspectiveTransform(test_point, self.homography_matrix)
                        tx, ty = test_result[0][0]
                        print(f"Test point: ({x}, {y}) -> ({tx}, {ty})")
                        
                        # Check if transformed point is within reasonable bounds (extended field)
                        if -50 <= tx < self.field_width*10 + 50 and -50 <= ty < self.field_height*10 + 50:
                            valid_count += 1
                        else:
                            print(f"Warning: Test point ({x}, {y}) transformed to ({tx}, {ty}), which is far outside field")
                    except Exception as e:
                        print(f"Error testing homography with point ({x}, {y}): {str(e)}")
                
                # If less than 3 test points transform to reasonable coordinates, warn the user
                if valid_count < 3:
                    print("Warning: Homography matrix may be invalid. Most test points transform outside field.")
                    self.instruction_label.config(text="Warning: Homography may be invalid. Try different points.")
                    # We still return True as the user may want to proceed anyway
                
                # Enable process video button and reference segment button when homography is computed
                if self.homography_matrix is not None:
                    self.process_video_btn.config(state=tk.NORMAL)
                    self.reference_btn.config(state=tk.NORMAL)
                    self.instruction_label.config(text="Homography computed. Click 'Select 5-Yard Segment' to set reference.")
                
                return True
            except Exception as e:
                print(f"Error computing homography: {str(e)}")
                self.instruction_label.config(text=f"Error: {str(e)}. Try different points.")
                return False
        return False

    def detect_players(self):
        if self.homography_matrix is None:
            print("Homography matrix not computed yet")
            self.instruction_label.config(text="Error: Homography matrix not computed. Reset and try again.")
            return
        start_time = time.time()
        try:
            _, img_encoded = cv2.imencode('.jpg', self.original_frame)
            img_bytes = img_encoded.tobytes()
            if self.detection_mode == 'player_ref':
                results = self.model_player_ref.predict_by_bytes(img_bytes, input_type="image")
                concepts = self.concepts_player_ref
            else:
                results = self.model_yard.predict_by_bytes(img_bytes, input_type="image")
                concepts = self.concepts_yard
            regions = results.outputs[0].data.regions
            print(f"Found {len(regions)} regions from model")
            print(f"Detection mode: {self.detection_mode}")
            print(f"Looking for concepts: {concepts}")
            
            # Debug: print structure of first region
            if regions:
                first_region = regions[0]
                print(f"First region attributes: {dir(first_region)}")
                if hasattr(first_region, 'data'):
                    print(f"First region data attributes: {dir(first_region.data)}")
                    if hasattr(first_region.data, 'concepts'):
                        print(f"First region concepts: {first_region.data.concepts}")
                        if first_region.data.concepts:
                            print(f"First concept attributes: {dir(first_region.data.concepts[0])}")
            
            pred_frame = self.original_frame.copy()
            field_with_players = self.field_img.copy()
            self.player_positions = []
            detection_count = 0
            colors = [
                (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255),
                (128, 0, 0), (0, 128, 0), (0, 0, 128), (128, 128, 0), (255, 165, 0), (128, 0, 128),
                (255, 192, 203), (192, 192, 192), (255, 255, 255), (0, 0, 0), (218, 165, 32),
                (70, 130, 180), (127, 255, 212), (139, 69, 19)
            ]
            for i, region in enumerate(regions):
                try:
                    # Check if region has concepts and filter by them
                    should_process = True
                    if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                        try:
                            region_concepts = [c.name for c in region.data.concepts]
                            should_process = any(concept in region_concepts for concept in concepts)
                            print(f"Region {i}: concepts {region_concepts}, should_process={should_process}")
                            if not should_process:
                                print(f"Skipping region {i}: concepts {region_concepts} don't match {concepts}")
                                continue
                        except Exception as e:
                            print(f"Error checking concepts for region {i}: {e}")
                            should_process = True
                    else:
                        print(f"Region {i}: no concepts found, processing anyway")
                    
                    # Get bounding box
                    bbox = region.region_info.bounding_box
                    x1 = int(bbox.left_col * self.width)
                    y1 = int(bbox.top_row * self.height)
                    x2 = int(bbox.right_col * self.width)
                    y2 = int(bbox.bottom_row * self.height)
                    
                    # Get confidence ONLY from first concept
                    conf = 0.0
                    if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                        concepts_list = region.data.concepts
                        if concepts_list and hasattr(concepts_list[0], 'value'):
                            conf = concepts_list[0].value
                    print(f"Region {i}: confidence={conf:.3f}")
                    
                    if conf < self.conf_threshold:
                        print(f"Skipping region {i}: confidence {conf:.3f} below threshold {self.conf_threshold}")
                        continue
                    
                    # Calculate foot position
                    foot_x = int((x1 + x2) / 2)
                    foot_y = int(y2)
                    
                    # Get color for this detection
                    color_idx = i % len(colors)
                    color = colors[color_idx]
                    
                    # Draw on original frame
                    cv2.rectangle(pred_frame, (x1, y1), (x2, y2), color, 2)
                    cv2.circle(pred_frame, (foot_x, foot_y), 5, color, -1)
                    
                    # Add confidence text
                    conf_text = f"{conf:.2f}"
                    cv2.putText(pred_frame, conf_text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Transform to field coordinates
                    try:
                        player_pos = np.array([[[foot_x, foot_y]]], dtype=np.float32)
                        transformed_pos = cv2.perspectiveTransform(player_pos, self.homography_matrix)
                        tx, ty = transformed_pos[0][0]
                        tx, ty = int(tx), int(ty)
                        
                        # Check if point is within field boundaries
                        if 0 <= tx < self.field_width*10 and 0 <= ty < self.field_height*10:
                            # Store player position in field coordinates
                            self.player_positions.append((tx, ty))
                            
                            # Draw on field
                            cv2.circle(field_with_players, (tx, ty), 8, color, -1)
                            player_num = i + 1
                            cv2.putText(field_with_players, str(player_num), (tx+5, ty+5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                            
                            detection_count += 1
                            print(f"Detection {i}: conf={conf:.3f}, pos=({tx},{ty})")
                        else:
                            print(f"Point ({tx},{ty}) is outside field boundaries")
                    except Exception as e:
                        print(f"Error transforming point: {str(e)}")
                        
                except Exception as e:
                    print(f"Error processing detection {i}: {str(e)}")
                    continue
            self.last_field_with_players = field_with_players.copy()
            pred_frame_rgb = cv2.cvtColor(pred_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(pred_frame_rgb)
            img = img.resize((int(self.width * 0.8), int(self.height * 0.8)))
            self.tk_img = ImageTk.PhotoImage(image=img)
            self.canvas.itemconfig(self.canvas_img, image=self.tk_img)
            field_with_players_rgb = cv2.cvtColor(field_with_players, cv2.COLOR_BGR2RGB)
            field_pil = Image.fromarray(field_with_players_rgb)
            self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
            self.field_canvas.itemconfig(self.field_canvas_img, image=self.field_tk_img)
            self.root.update_idletasks()
            if detection_count > 0:
                self.save_btn.config(state=tk.NORMAL)
            elapsed_time = time.time() - start_time
            print(f"Detected {detection_count} objects in {elapsed_time:.2f} seconds")
            self.instruction_label.config(text=f"Detected {detection_count} objects. Confidence threshold: {self.conf_threshold}")
        except Exception as e:
            print(f"Error in detect_players: {str(e)}")
            import traceback
            traceback.print_exc()
            self.instruction_label.config(text=f"Error detecting players: {str(e)}")
            rgb_frame = cv2.cvtColor(self.original_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            img = img.resize((int(self.width * 0.8), int(self.height * 0.8)))
            self.tk_img = ImageTk.PhotoImage(image=img)
            self.canvas.itemconfig(self.canvas_img, image=self.tk_img)
            field_img_rgb = cv2.cvtColor(self.field_img, cv2.COLOR_BGR2RGB)
            field_pil = Image.fromarray(field_img_rgb)
            self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
            self.field_canvas.itemconfig(self.field_canvas_img, image=self.field_tk_img)
        finally:
            if 'temp_file' in locals():
                os.unlink(temp_file.name)

    def save_field_image(self):
        if self.last_field_with_players is None:
            print("No field image with players to save")
            return
            
        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            title="Save Bird's Eye View Image"
        )
        
        if file_path:
            try:
                cv2.imwrite(file_path, self.last_field_with_players)
                print(f"Bird's eye view image saved to {file_path}")
                self.instruction_label.config(text=f"Image saved to {file_path}")
            except Exception as e:
                print(f"Error saving image: {str(e)}")
                self.instruction_label.config(text=f"Error saving image: {str(e)}")

    def draw_players_on_field(self, player_coordinates):
        try:
            if self.homography_matrix is None:
                print("No homography matrix available")
                self.instruction_label.config(text="Error: No homography matrix available")
                return None
                
            field_with_players = self.field_img.copy()
            
            print(f"Drawing {len(player_coordinates)} players on field")
            
            # Draw each player on the field
            for i, (cx, cy) in enumerate(player_coordinates):
                try:
                    # Convert player coordinate to field coordinate
                    player_point = np.array([[[cx, cy]]], dtype=np.float32)
                    field_point = cv2.perspectiveTransform(player_point, self.homography_matrix)
                    
                    # Extract the x, y coordinates
                    field_x, field_y = int(field_point[0][0][0]), int(field_point[0][0][1])
                    
                    # Check if the transformed point is within the field boundaries
                    if 0 <= field_x < self.field_width*10 and 0 <= field_y < self.field_height*10:
                        # Use consistent radius (8) as in detect_players
                        cv2.circle(field_with_players, (field_x, field_y), 8, (0, 0, 255), -1)
                        # Draw player number
                        cv2.putText(field_with_players, str(i+1), (field_x+5, field_y+5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                        
                        print(f"Player {i+1}: Video ({cx}, {cy}) -> Field ({field_x}, {field_y})")
                    else:
                        print(f"Player {i+1} coordinates outside field: ({field_x}, {field_y})")
                except Exception as e:
                    print(f"Error placing player {i+1}: {str(e)}")
                    continue
                    
            return field_with_players
        except Exception as e:
            print(f"Error in draw_players_on_field: {str(e)}")
            self.instruction_label.config(text=f"Error drawing players: {str(e)}")
            # Return the original field as fallback
            return self.field_img.copy() if hasattr(self, 'field_img') else None

    def show_debug_info(self):
        """Print debug information about the current state of the application"""
        print("\n=== DEBUG INFORMATION ===")
        
        # Field image info
        print(f"Field Image Size: {self.field_img.shape if hasattr(self, 'field_img') else 'Not loaded'}")
        print(f"Field Dimensions: {self.field_width}x{self.field_height} yards (x10 pixels)")
        
        # Homography info
        if self.homography_matrix is not None:
            print("\nHomography Matrix:")
            print(self.homography_matrix)
            
            # Test some sample points to verify transformation
            test_points = [
                (self.width//2, self.height//2),  # center
                (0, 0),                          # top-left
                (self.width-1, 0),               # top-right
                (0, self.height-1),              # bottom-left
                (self.width-1, self.height-1)    # bottom-right
            ]
            
            print("\nTest Point Transformations (Video → Field):")
            for i, (x, y) in enumerate(test_points):
                try:
                    test_point = np.array([[[x, y]]], dtype=np.float32)
                    test_result = cv2.perspectiveTransform(test_point, self.homography_matrix)
                    tx, ty = test_result[0][0]
                    print(f"  Point {i+1}: ({x},{y}) → ({tx:.1f},{ty:.1f})")
                    
                    # Check if the point is within field boundaries
                    in_bounds = 0 <= tx < self.field_width*10 and 0 <= ty < self.field_height*10
                    print(f"    Within field boundaries: {in_bounds}")
                except Exception as e:
                    print(f"  Error transforming point {i+1}: {str(e)}")
            
            # Show info about stored player positions
            print(f"\nStored Player Positions (in field coordinates): {len(self.player_positions)}")
            for i, (px, py) in enumerate(self.player_positions):
                print(f"  Player {i+1}: ({px}, {py})")
        else:
            print("\nHomography matrix not computed yet")
            print("Please select points on both the video and field to compute homography")
        
        # Detection settings
        print(f"\nDetection Settings:")
        print(f"  Confidence Threshold: {self.conf_threshold}")
        print(f"  Detection Class: {self.detection_mode}")
        print(f"  Number of Keypoints: {self.num_keypoints}")
        
        # UI state
        print(f"\nUI State:")
        print(f"  Selecting Source: {self.selecting_source}")
        print(f"  Source Complete: {self.source_complete}")
        print(f"  Destination Complete: {self.dest_complete}")
        print(f"  Source Points: {len(self.source_points)}")
        print(f"  Destination Points: {len(self.destination_points)}")
        
        print("=== END DEBUG INFO ===\n")
        
        # Update the instruction label
        if self.homography_matrix is None:
            self.instruction_label.config(text="Debug: Homography matrix not computed yet")
        else:
            self.instruction_label.config(text=f"Debug: {len(self.player_positions)} players mapped")

    def run(self):
        self.root.mainloop()

    def create_output_directory(self):
        """Create output directory and return paths"""
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_original_path = os.path.join(output_dir, 'output_original.mp4')
        output_field_path = os.path.join(output_dir, 'output_field.mp4')
        return output_original_path, output_field_path

    def process_video(self):
        """Process entire video with segmentation masks and camera motion compensation"""
        try:
            if self.homography_matrix is None:
                print("Error: Homography matrix not computed yet")
                return

            # Clear any manually placed keypoint graphics from the canvas
            self.canvas.delete("all")
            self.field_canvas.delete("all")
            
            # Redraw clean images without keypoints
            rgb_frame = cv2.cvtColor(self.original_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            img = img.resize((int(self.width * 0.8), int(self.height * 0.8)))
            self.tk_img = ImageTk.PhotoImage(image=img)
            
            field_img_rgb = cv2.cvtColor(self.field_img, cv2.COLOR_BGR2RGB)
            field_pil = Image.fromarray(field_img_rgb)
            self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
            
            # Create new canvas images with clean starting frames
            self.canvas_img = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
            self.field_canvas_img = self.field_canvas.create_image(0, 0, anchor=tk.NW, image=self.field_tk_img)
            
            # Force UI update to show clean frames
            self.root.update()
            
            # Setup video capture
            cap = cv2.VideoCapture(self.video_path)
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f"Processing video: {total_frames} frames at {fps} FPS")
            
            # Store fps for speed calculations
            self.video_fps = fps
            
            # Create output directory and get paths
            output_original_path, output_field_path = self.create_output_directory()
            
            # Create video writers
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_original = cv2.VideoWriter(output_original_path, fourcc, fps, (self.width, self.height))
            out_field = cv2.VideoWriter(output_field_path, fourcc, fps, (self.field_width*10, self.field_height*10))

            # Initialize tracking variables
            base_homography = self.homography_matrix.copy()  # Base homography from initial keypoints
            current_homography = self.homography_matrix.copy()  # Will be updated with camera motion
            cumulative_motion = np.eye(3, 3, dtype=np.float32)  # Track cumulative camera motion
            self.player_tracks = {}  # Dictionary to store player tracks
            self.next_player_id = 1  # Counter for assigning unique player IDs
            self.max_tracking_distance = 20  # Maximum distance to consider for the same player
            self.track_history_length = 50  # Number of frames to keep in track history
            last_positions = []  # Store last frame's player positions
            
            # Reset camera motion tracking variables
            self.prev_frame = None
            self.prev_gray = None
            self.prev_keypoints = None
            self.motion_history = []
            
            # Initialize Kalman filter for motion prediction if not already done
            if self.use_kalman_filter and not hasattr(self, 'kalman'):
                # State: [dx, dy, ds, da, ddx, ddy, dds, dda] - position, scale, angle and their derivatives
                self.kalman = cv2.KalmanFilter(8, 4)
                # Measurement matrix (only position, scale and angle are measured directly)
                self.kalman.measurementMatrix = np.array([
                    [1, 0, 0, 0, 0, 0, 0, 0],
                    [0, 1, 0, 0, 0, 0, 0, 0],
                    [0, 0, 1, 0, 0, 0, 0, 0],
                    [0, 0, 0, 1, 0, 0, 0, 0]
                ], np.float32)
                # State transition matrix (includes velocity)
                self.kalman.transitionMatrix = np.array([
                    [1, 0, 0, 0, 1, 0, 0, 0],
                    [0, 1, 0, 0, 0, 1, 0, 0],
                    [0, 0, 1, 0, 0, 0, 1, 0],
                    [0, 0, 0, 1, 0, 0, 0, 1],
                    [0, 0, 0, 0, 1, 0, 0, 0],
                    [0, 0, 0, 0, 0, 1, 0, 0],
                    [0, 0, 0, 0, 0, 0, 1, 0],
                    [0, 0, 0, 0, 0, 0, 0, 1]
                ], np.float32)
                # Process noise
                self.kalman.processNoiseCov = np.eye(8, dtype=np.float32) * 0.03
                # Measurement noise - this is tuned for camera motion
                self.kalman.measurementNoiseCov = np.eye(4, dtype=np.float32) * 0.1
                # Initial state
                self.kalman.errorCovPost = np.eye(8, dtype=np.float32)
                self.kalman.statePost = np.zeros((8, 1), np.float32)
                self.kalman_initialized = False

            # Add progress bar and more detailed status display
            progress_frame = Frame(self.root)
            progress_frame.pack(fill=tk.X, pady=5)
            
            # Status label
            status_label = Label(progress_frame, text="Processing video...", font=("Arial", 10, "bold"))
            status_label.pack(side=tk.TOP)
            
            # Frame counter
            progress_label = Label(progress_frame, text="Frame: 0/0")
            progress_label.pack(side=tk.TOP)
            
            # Progress bar
            progress_var = tk.DoubleVar()
            progress_bar = Scale(progress_frame, from_=0, to=100, orient=HORIZONTAL, 
                               length=400, showvalue=False, variable=progress_var)
            progress_bar.pack(side=tk.TOP, fill=tk.X, padx=5)
            
            # Player count label
            player_count_label = Label(progress_frame, text="Tracking: 0 players")
            player_count_label.pack(side=tk.TOP)
            
            # Keypoint count label
            keypoint_label = Label(progress_frame, text="Keypoints: 0")
            keypoint_label.pack(side=tk.TOP)
            
            # Camera motion indicator
            motion_label = Label(progress_frame, text="Camera motion: Initializing")
            motion_label.pack(side=tk.TOP)

            # Get skip frames value from UI control
            skip_frames = self.skip_frames_var.get()
            if skip_frames < 1:
                skip_frames = 1  # Ensure minimum of 1 (process every frame)
                
            print(f"Processing every {skip_frames} frame(s)")
            
            # Optimization parameters
            MOTION_TRACKING_INTERVAL = 1  # Update motion tracking every N frames
            MASK_CACHE = {}  # Cache for segmentation masks
            HIGH_CONF_THRESHOLD = 0.7  # Only apply masks to high confidence detections

            # Display segmentation status to the user
            segmentation_status = "enabled" if hasattr(self, 'segmentation_available') and self.segmentation_available else "disabled"
            segmentation_label = Label(progress_frame, text=f"Segmentation: {segmentation_status}")
            segmentation_label.pack(side=tk.TOP)

            # Add variables for homography recomputation
            HOMOGRAPHY_RECOMPUTE_INTERVAL = 1  # Recompute every frame
            last_homography_recompute = 0
            keypoint_history = []  # Store recent keypoints for homography recomputation
            MAX_KEYPOINT_HISTORY = 2000  # Increased from 1000 to store more keypoints

            # Main processing loop
            frame_count = 0
            actual_frame_count = 0
            last_ui_update_time = time.time()

            # Initialize canvas items if they don't exist
            if not hasattr(self, 'canvas_img') or not self.canvas.find_withtag(self.canvas_img):
                self.canvas.delete("all")
                self.canvas_img = self.canvas.create_image(0, 0, anchor=tk.NW, image=None)

            if not hasattr(self, 'field_canvas_img') or not self.field_canvas.find_withtag(self.field_canvas_img):
                self.field_canvas.delete("all")
                self.field_canvas_img = self.field_canvas.create_image(0, 0, anchor=tk.NW, image=None)

            # Save original image before processing in case we need it
            self.orig_ui_image = self.tk_img
            self.orig_field_image = self.field_tk_img

            # Store motion vectors for visualization
            self.tracking_history = []

            # Add stop processing button
            self.stop_processing = False
            stop_btn = Button(progress_frame, text="Stop Processing & Save", 
                             command=self.stop_video_processing,
                             bg="red", fg="white", font=("Arial", 10, "bold"))
            stop_btn.pack(side=tk.TOP, pady=5, padx=10, fill=tk.X)

            # Add field of view visualization
            field_of_view_frame = self.field_img.copy()
            
            while True:
                # Check if stop requested
                if self.stop_processing:
                    print("Stop processing requested. Saving progress...")
                    break  # Exit the processing loop
                    
                # Read frame
                ret, frame = cap.read()
                if not ret:
                    break  # End of video
                
                actual_frame_count += 1
                
                # Skip frames if needed
                if (actual_frame_count - 1) % skip_frames != 0:
                    continue
                
                frame_count += 1
                
                # Update frame counter for temporal smoothing
                self.frame_count = frame_count
                
                # Update status
                status_label.config(text=f"Processing video... Frame {frame_count}")
                progress = (actual_frame_count / total_frames) * 100
                progress_var.set(progress)
                progress_label.config(text=f"Frame {frame_count} (actual: {actual_frame_count}/{total_frames}) - {progress:.1f}%")
                
                # Force UI update to show progress before processing begins
                self.root.update()
                
                # Create a clean tracking visualization copy of the frame
                tracking_vis = frame.copy()
                
                # Update camera motion and homography each frame
                if frame_count % MOTION_TRACKING_INTERVAL == 0:
                    # If using Kalman filter, predict next motion before measurement
                    if self.use_kalman_filter and self.kalman_initialized:
                        self.kalman.predict()
                    
                    # Get actual motion measurement
                    motion_matrix, tracking_quality = self.update_camera_motion(frame, keypoint_history)
                    
                    if motion_matrix is not None:
                        # Calculate motion magnitude for adaptive parameters
                        motion_mag = self.analyze_motion_magnitude(motion_matrix)
                        
                        # Update tracking parameters based on motion magnitude
                        self.adaptive_ransac_threshold = min(
                            self.max_ransac_threshold,
                            max(self.min_ransac_threshold, 3.0 + motion_mag * 0.1)
                        )
                        
                        # Update UI with estimation quality
                        if tracking_quality > 0.8:
                            quality_text = "Excellent"
                            self.instruction_label.config(text=f"Motion Estimation Quality: {quality_text}")
                        elif tracking_quality > 0.6:
                            quality_text = "Good"
                            self.instruction_label.config(text=f"Motion Estimation Quality: {quality_text}")
                        elif tracking_quality > 0.4:
                            quality_text = "Fair"
                            self.instruction_label.config(text=f"Motion Estimation Quality: {quality_text}")
                        else:
                            quality_text = "Poor"
                            self.instruction_label.config(text=f"Motion Estimation Quality: {quality_text}")
                        
                        # If using Kalman filter, correct prediction with measurement
                        if self.use_kalman_filter:
                            # Extract motion parameters for Kalman update
                            tx = motion_matrix[0, 2]  # x translation
                            ty = motion_matrix[1, 2]  # y translation
                            
                            # Approximate scale and rotation from matrix (simplified)
                            a = motion_matrix[0, 0]
                            b = motion_matrix[0, 1]
                            c = motion_matrix[1, 0]
                            d = motion_matrix[1, 1]
                            
                            scale = np.sqrt(a*a + c*c)  # Approximate scale
                            angle = np.arctan2(c, a)    # Approximate rotation angle
                            
                            # Update Kalman filter with measurement
                            measurement = np.array([[tx], [ty], [scale], [angle]], np.float32)
                            
                            if not self.kalman_initialized:
                                # Initialize Kalman state with first measurement
                                self.kalman.statePost = np.array([
                                    [tx], [ty], [scale], [angle], [0], [0], [0], [0]
                                ], np.float32)
                                self.kalman_initialized = True
                            else:
                                # Correct Kalman prediction with new measurement
                                corrected_state = self.kalman.correct(measurement)
                                
                                # Get predicted motion parameters
                                pred_tx = corrected_state[0, 0]
                                pred_ty = corrected_state[1, 0]
                                pred_scale = corrected_state[2, 0]
                                pred_angle = corrected_state[3, 0]
                                
                                # Blend prediction with measurement based on confidence
                                # Less confident (lower tracking_quality) → more smoothing
                                blend_ratio = min(0.8, max(0.2, tracking_quality))
                                
                                # Create smoothed motion matrix
                                cos_angle = np.cos(pred_angle)
                                sin_angle = np.sin(pred_angle)
                                
                                # Build a new motion matrix from filtered parameters
                                smooth_matrix = np.array([
                                    [pred_scale * cos_angle, -pred_scale * sin_angle, pred_tx],
                                    [pred_scale * sin_angle, pred_scale * cos_angle, pred_ty],
                                    [0, 0, 1]
                                ], np.float32)
                                
                                # Blend with original motion matrix
                                motion_matrix = (motion_matrix * blend_ratio + 
                                                smooth_matrix * (1 - blend_ratio))
                        
                        # Add to motion history for temporal smoothing
                        self.motion_history.append(motion_matrix)
                        if len(self.motion_history) > self.motion_history_size:
                            self.motion_history.pop(0)
                        
                        # Apply temporal smoothing - weighted average of recent motions
                        if len(self.motion_history) > 1:
                            # Use exponential weighting - more recent frames have higher weight
                            weights = np.array([np.exp(i) for i in range(len(self.motion_history))])
                            weights = weights / np.sum(weights)  # Normalize weights
                            
                            # Initialize smoothed matrix
                            smoothed_matrix = np.zeros_like(motion_matrix)
                            
                            # Compute weighted average
                            for i, mat in enumerate(self.motion_history):
                                smoothed_matrix += mat * weights[i]
                            
                            # Use smoothed matrix instead of current frame's matrix
                            # This reduces jitter in fast movements
                            motion_matrix = smoothed_matrix
                        
                        # Update cumulative motion matrix 
                        cumulative_motion = cumulative_motion @ motion_matrix
                        
                        # Calculate the current homography by combining base homography with inverse camera motion
                        try:
                            # Invert the cumulative motion
                            inverse_motion = cv2.invert(cumulative_motion)[1]
                            
                            # Apply to the original homography - this is the correct way to handle camera motion
                            current_homography = base_homography @ inverse_motion
                            
                            # Calculate motion magnitude for UI display
                            tx = motion_matrix[0, 2]  # x translation
                            ty = motion_matrix[1, 2]  # y translation
                            motion_mag = np.sqrt(tx*tx + ty*ty)
                            
                            # Update motion info in UI
                            motion_label.config(text=f"Camera motion: {motion_mag:.1f} pixels")
                            
                            # Update field of view points using current homography
                            if current_homography is not None:
                                # Get the four corners of the frame
                                corners = np.array([
                                    [0, 0],  # top-left
                                    [self.width-1, 0],  # top-right
                                    [self.width-1, self.height-1],  # bottom-right
                                    [0, self.height-1]  # bottom-left
                                ], dtype=np.float32).reshape(-1, 1, 2)
                                
                                # Transform corners to field coordinates
                                field_corners = cv2.perspectiveTransform(corners, current_homography)
                                
                                # Store the transformed corners as field of view points
                                self.field_of_view_points = field_corners.reshape(-1, 2).astype(np.int32)
                                
                                # Also add these points to keypoint history for homography computation
                                for corner in field_corners:
                                    keypoint_history.append((corner.reshape(2), 1.0))  # Add with high quality score
                                
                                # Trim keypoint history if needed
                                if len(keypoint_history) > MAX_KEYPOINT_HISTORY:
                                    keypoint_history = keypoint_history[-MAX_KEYPOINT_HISTORY:]
                        
                        except cv2.error as e:
                            print(f"Error inverting motion matrix: {e}")
                            # If inversion fails, don't update homography this frame
                            motion_label.config(text="Camera motion: Matrix error")
                        
                        # Update keypoint info in UI
                        if hasattr(self, 'prev_keypoints') and self.prev_keypoints is not None:
                            keypoint_count = len(self.prev_keypoints)
                            keypoint_label.config(text=f"Keypoints: {keypoint_count}")
                        else:
                            keypoint_label.config(text="Keypoints: 0")
                    else:
                        # If motion tracking failed but we have history, use predicted motion
                        if self.use_kalman_filter and self.kalman_initialized:
                            # Get predicted state from Kalman filter
                            predicted_state = self.kalman.statePost
                            
                            # Extract predicted motion parameters
                            pred_tx = predicted_state[0, 0]
                            pred_ty = predicted_state[1, 0]
                            pred_scale = predicted_state[2, 0]
                            pred_angle = predicted_state[3, 0]
                            
                            # Create predicted motion matrix
                            cos_angle = np.cos(pred_angle)
                            sin_angle = np.sin(pred_angle)
                            
                            # Build a new motion matrix from predicted parameters
                            predicted_matrix = np.array([
                                [pred_scale * cos_angle, -pred_scale * sin_angle, pred_tx],
                                [pred_scale * sin_angle, pred_scale * cos_angle, pred_ty],
                                [0, 0, 1]
                            ], np.float32)
                            
                            # Use predicted motion with low confidence
                            # This helps maintain continuity during tracking failures
                            predicted_matrix = predicted_matrix * 0.3 + np.eye(3) * 0.7
                            
                            # Update cumulative motion and homography
                            cumulative_motion = cumulative_motion @ predicted_matrix
                            
                            try:
                                inverse_motion = cv2.invert(cumulative_motion)[1]
                                current_homography = base_homography @ inverse_motion
                                motion_label.config(text="Camera motion: Using prediction")
                            except cv2.error:
                                # Fall back to previous homography
                                motion_label.config(text="Camera motion: Prediction failed")
                        else:
                            # If motion tracking failed and no prediction available
                            motion_label.config(text="Camera motion: Tracking failed")
                            print("Warning: Motion tracking failed for this frame")
                
                # Convert frame to bytes for Clarifai
                _, img_encoded = cv2.imencode('.jpg', frame)
                img_bytes = img_encoded.tobytes()

                # Detect players using Clarifai
                results = self.model_player_ref.predict_by_bytes(img_bytes, input_type="image")
                regions = results.outputs[0].data.regions

                # Also detect yard markers for visualization
                yard_results = self.model_yard.predict_by_bytes(img_bytes, input_type="image")
                yard_regions = yard_results.outputs[0].data.regions

                # Define concepts based on detection mode
                concepts = self.concepts_player_ref if self.detection_mode == 'player_ref' else self.concepts_yard

                # Create visualization frames
                vis_frame = frame.copy()
                field_view = self.field_img.copy()

                # Draw field of view boundary on the field view
                if hasattr(self, 'field_of_view_points') and len(self.field_of_view_points) >= 3:
                    # Convert points to numpy array for drawing
                    fov_points = np.array(self.field_of_view_points, dtype=np.int32)
                    
                    # Create a darkened overlay of the entire field view
                    alpha = 0.5 # Transparency level for the outside area
                    overlay = field_view.copy()
                    cv2.addWeighted(overlay, 1 - alpha, np.zeros_like(overlay), alpha, 0, overlay)

                    # Create mask for the area *inside* the field of view polygon
                    mask = np.zeros(field_view.shape[:2], dtype=np.uint8)
                    cv2.fillPoly(mask, [fov_points], 255) # White inside the polygon
                    
                    # Where the mask is white (inside polygon), copy original bright pixels onto the overlay
                    overlay[mask == 255] = field_view[mask == 255]
                    
                    # Use the overlay as the new field_view
                    field_view = overlay
                    
                    # Draw the field of view boundary (on the now correctly masked view)
                    cv2.polylines(field_view, [fov_points], True, (0, 255, 255), 2) # Yellow boundary
                    
                    # Add to history for smoothing
                    self.field_of_view_history.append(fov_points)
                    if len(self.field_of_view_history) > self.max_fov_history:
                        self.field_of_view_history.pop(0)
                    
                    # If we have history, draw a smoothed boundary
                    if len(self.field_of_view_history) > 1:
                        # Average the points from history
                        smoothed_points = np.mean(self.field_of_view_history, axis=0).astype(np.int32)
                        cv2.polylines(field_view, [smoothed_points], True, (0, 200, 255), 1) # Slightly different color for smoothed
                    
                    # Draw camera center point
                    center = np.mean(fov_points, axis=0).astype(np.int32)
                    # cv2.circle(field_view, tuple(center), 5, (0, 255, 255), -1) # Yellow center

                # Store current frame's player positions
                current_positions = []
                current_detections = []
                
                # Also create a mask of player positions for camera motion tracking
                player_mask = np.ones((self.height, self.width), dtype=np.uint8) * 255
                
                # Pre-process detections to merge body part detections of the same player
                raw_detections = []
                for region in regions:
                    try:
                        # Check if region has concepts and filter by them (same as detect_players)
                        should_process = True
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            try:
                                region_concepts = [c.name for c in region.data.concepts]
                                should_process = any(concept in region_concepts for concept in concepts)
                                if not should_process:
                                    continue
                            except Exception as e:
                                print(f"Error checking concepts for region: {e}")
                                should_process = True
                        else:
                            print("Region has no concepts, processing anyway")
                        
                        # Get confidence ONLY from first concept (same as detect_players)
                        conf = 0.0
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            concepts_list = region.data.concepts
                            if concepts_list and hasattr(concepts_list[0], 'value'):
                                conf = concepts_list[0].value
                        
                        if conf < self.conf_threshold:
                            continue

                        # Get bounding box
                        bbox = region.region_info.bounding_box
                        x1 = int(bbox.left_col * self.width)
                        y1 = int(bbox.top_row * self.height)
                        x2 = int(bbox.right_col * self.width)
                        y2 = int(bbox.bottom_row * self.height)
                        
                        # Calculate foot position
                        foot_x = int((x1 + x2) / 2)
                        foot_y = y2
                        
                        raw_detections.append({
                            'bbox': (x1, y1, x2, y2),
                            'foot': (foot_x, foot_y),
                            'conf': conf,
                            'region': region
                        })
                    except Exception as e:
                        print(f"Error processing detection: {str(e)}")
                
                # Merge nearby detections that are likely the same player (body parts)
                merged_detections = []
                used_detections = set()
                
                for i, det1 in enumerate(raw_detections):
                    if i in used_detections:
                        continue
                    
                    # Find nearby detections that might be the same player
                    nearby_detections = [det1]
                    nearby_indices = [i]
                    
                    for j, det2 in enumerate(raw_detections):
                        if j <= i or j in used_detections:
                            continue
                        
                        # Calculate distance between foot positions
                        foot1 = det1['foot']
                        foot2 = det2['foot']
                        dist = np.sqrt((foot2[0] - foot1[0])**2 + (foot2[1] - foot1[1])**2)
                        
                        # If detections are very close, they might be the same player
                        if dist < 30:  # Increased threshold for body part detection
                            # Check if bounding boxes overlap significantly
                            bbox1 = det1['bbox']
                            bbox2 = det2['bbox']
                            
                            # Calculate intersection over union (IoU)
                            x1_1, y1_1, x2_1, y2_1 = bbox1
                            x1_2, y1_2, x2_2, y2_2 = bbox2
                            
                            # Calculate intersection
                            x1_i = max(x1_1, x1_2)
                            y1_i = max(y1_1, y1_2)
                            x2_i = min(x2_1, x2_2)
                            y2_i = min(y2_1, y2_2)
                            
                            if x1_i < x2_i and y1_i < y2_i:
                                intersection = (x2_i - x1_i) * (y2_i - y1_i)
                                area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
                                area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
                                union = area1 + area2 - intersection
                                iou = intersection / union if union > 0 else 0
                                
                                # If high IoU or very close, merge them
                                if iou > 0.1 or dist < 15:
                                    nearby_detections.append(det2)
                                    nearby_indices.append(j)
                                    used_detections.add(j)
                                    print(f"Found nearby detections: dist={dist:.1f}, IoU={iou:.2f}")
                    
                    # Merge nearby detections
                    if len(nearby_detections) > 1:
                        # Use the detection with highest confidence as the primary one
                        best_detection = max(nearby_detections, key=lambda x: x['conf'])
                        merged_detections.append(best_detection)
                        print(f"Merged {len(nearby_detections)} nearby detections into single detection")
                        
                        # Also merge any existing tracks that correspond to these detections
                        self.merge_corresponding_tracks(nearby_detections)
                    else:
                        merged_detections.append(det1)
                    
                    used_detections.add(i)
                
                # Use merged detections for processing
                regions = [det['region'] for det in merged_detections]

                # Process each detection
                for region in regions:
                    try:
                        # Check if region has concepts and filter by them (same as detect_players)
                        should_process = True
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            try:
                                region_concepts = [c.name for c in region.data.concepts]
                                should_process = any(concept in region_concepts for concept in concepts)
                                if not should_process:
                                    continue
                            except Exception as e:
                                print(f"Error checking concepts for region: {e}")
                                should_process = True
                        else:
                            print("Region has no concepts, processing anyway")
                        
                        # Get confidence ONLY from first concept (same as detect_players)
                        conf = 0.0
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            concepts_list = region.data.concepts
                            if concepts_list and hasattr(concepts_list[0], 'value'):
                                conf = concepts_list[0].value
                        
                        if conf < self.conf_threshold:
                            continue

                        # Get bounding box
                        bbox = region.region_info.bounding_box
                        x1 = int(bbox.left_col * self.width)
                        y1 = int(bbox.top_row * self.height)
                        x2 = int(bbox.right_col * self.width)
                        y2 = int(bbox.bottom_row * self.height)
                        
                        # Mask out player region from camera tracking
                        cv2.rectangle(player_mask, (x1, y1), (x2, y2), 0, -1)
                        
                        # Add padding around player for better exclusion
                        padding = 10
                        x1_pad = max(0, x1 - padding)
                        y1_pad = max(0, y1 - padding)
                        x2_pad = min(self.width, x2 + padding)
                        y2_pad = min(self.height, y2 + padding)
                        #cv2.rectangle(player_mask, (x1_pad, y1_pad), (x2_pad, y2_pad), 0, -1)

                        # Calculate foot position
                        foot_x = int((x1 + x2) / 2)
                        foot_y = y2

                        # Transform to field coordinates using current homography
                        player_pos = np.array([[[foot_x, foot_y]]], dtype=np.float32)
                        transformed_pos = cv2.perspectiveTransform(player_pos, current_homography)
                        tx, ty = map(int, transformed_pos[0][0])

                        # Store position if within bounds
                        if 0 <= tx < self.field_width*10 and 0 <= ty < self.field_height*10:
                            # Find or create player ID
                            player_id = None
                            min_dist = float('inf')
                            
                            # Try to match with existing tracks
                            for pid, track in self.player_tracks.items():
                                if track['positions']:
                                    last_pos = track['positions'][-1]
                                    dist = np.sqrt((tx - last_pos[0])**2 + (ty - last_pos[1])**2)
                                    if dist < self.max_tracking_distance and dist < min_dist:
                                        min_dist = dist
                                        player_id = pid
                            
                            # If no match found, create new track
                            if player_id is None:
                                player_id = self.next_player_id
                                self.next_player_id += 1
                            
                            current_positions.append((tx, ty))
                            current_detections.append({
                                'bbox': (x1, y1, x2, y2),
                                'foot': (foot_x, foot_y),
                                'field_pos': (tx, ty),
                                'player_id': player_id,
                                'conf': conf
                            })
                    except Exception as e:
                        print(f"Error processing detection: {str(e)}")

                # Apply temporal smoothing to current positions
                smoothed_positions = self.smooth_positions_temporally(current_positions, frame_count)
                
                # Interpolate positions for frames between detections
                self.interpolate_positions_between_frames(smoothed_positions, frame_count)
                
                # Update player tracks with smoothed positions
                self.update_player_tracks(smoothed_positions)
                
                # Apply velocity smoothing
                self.apply_velocity_smoothing()
                
                # Update last processed frame
                self.last_processed_frame = frame_count
                
                # Clear old interpolated positions to prevent memory buildup
                if frame_count % 10 == 0:  # Clear every 10 frames
                    self.interpolated_positions.clear()
                
                player_count_label.config(text=f"Tracking: {len(self.player_tracks)} players")

                # Store tracking data for this frame
                frame_tracking_data = []
                for track_id, track in self.player_tracks.items():
                    if track['positions']:
                        last_pos = track['positions'][-1]
                        frame_tracking_data.append({
                            'id': track_id,
                            'x': last_pos[0],
                            'y': last_pos[1],
                            'speed': track.get('speed', 0),
                            'velocity_x': track.get('velocity', (0, 0))[0],
                            'velocity_y': track.get('velocity', (0, 0))[1]
                        })
                self.tracking_history.append(frame_tracking_data)

                # Collect high confidence detections for batch segmentation
                high_conf_detections = []
                high_conf_bboxes = []
                high_conf_ids = []
                
                for detection in current_detections:
                    if detection['conf'] >= self.conf_threshold:
                        high_conf_detections.append(detection)
                        high_conf_bboxes.append(detection['bbox'])
                        high_conf_ids.append(detection['player_id'])
                
                # Apply segmentation masks to all detections at once
                # but process in a way compatible with SAM model
                batch_masks = []
                if high_conf_bboxes:
                    print(f"Processing segmentation for {len(high_conf_bboxes)} detections")
                    batch_masks = self.apply_segmentation_masks_batch(frame, high_conf_bboxes, high_conf_ids)
                
                # Draw visualizations on both frames
                # 1. Draw player boxes and IDs on the original frame
                for i, detection in enumerate(current_detections):
                    x1, y1, x2, y2 = detection['bbox']
                    foot_x, foot_y = detection['foot']
                    player_id = detection['player_id']
                    conf = detection['conf']
                    
                    color = self.get_player_color(player_id)
                    
                    # Draw bounding box
                    #cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)
                    
                    # Draw player ID
                    #cv2.putText(vis_frame, f"ID:{player_id}", (x1, y1 - 10), 
                    #           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Draw confidence
                    conf_text = f"{conf*100:.0f}%"
                    cv2.putText(vis_frame, conf_text, (x1, y1 - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Draw speed if available
                    if player_id in self.player_tracks and 'speed' in self.player_tracks[player_id]:
                        speed = self.player_tracks[player_id]['speed']
                        speed_text = f"{speed:.1f}mph"
                        cv2.putText(vis_frame, speed_text, (x1, y1 - 25), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Draw foot position
                    cv2.circle(vis_frame, (foot_x, foot_y), 5, color, -1)
                    
                    # Apply segmentation mask for high confidence detections
                    if conf >= self.conf_threshold and i < len(batch_masks) and batch_masks[i] is not None:
                        # Apply the corresponding mask from the batch
                        mask = batch_masks[i]
                        
                        # Create a colored mask
                        colored_mask = np.zeros_like(frame)
                        colored_mask[mask > 0] = color
                        
                        # Also update player mask for camera tracking
                        player_mask[mask > 0] = 0
                        
                        # Blend the mask with the frame
                        alpha = 0.5  # Slightly reduce opacity to better see player features
                        vis_frame = cv2.addWeighted(vis_frame, 1, colored_mask, alpha, 0)
                        
                        # Draw ellipse with the same color
                        self.draw_ellipse(vis_frame, (x1, y1, x2, y2), color, player_id)
                
                # Store player mask for next camera motion update
                self.player_mask = player_mask

                # Draw yard markers FIRST (before players) for better visualization
                for region in yard_regions:
                    try:
                        # Check if region has concepts and filter by yard concepts
                        should_process = True
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            try:
                                region_concepts = [c.name for c in region.data.concepts]
                                should_process = any(concept in region_concepts for concept in self.concepts_yard)
                                if not should_process:
                                    continue
                            except Exception as e:
                                continue
                        
                        # Get confidence
                        conf = 0.0
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            concepts_list = region.data.concepts
                            if concepts_list and hasattr(concepts_list[0], 'value'):
                                conf = concepts_list[0].value
                        
                        # Only show high confidence yard markers
                        if conf < 0.3:  # Lower threshold for yard markers
                            continue
                        
                        # Get bounding box
                        bbox = region.region_info.bounding_box
                        x1 = int(bbox.left_col * self.width)
                        y1 = int(bbox.top_row * self.height)
                        x2 = int(bbox.right_col * self.width)
                        y2 = int(bbox.bottom_row * self.height)
                        
                        # Get concept name
                        concept_name = "unknown"
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            concepts_list = region.data.concepts
                            if concepts_list and hasattr(concepts_list[0], 'name'):
                                concept_name = concepts_list[0].name
                        
                        # Different visualization for different yard markers
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        
                        if concept_name in ["10", "20", "30", "40", "50"]:
                            color = (255, 0, 255)  # Magenta for yard numbers
                            cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(vis_frame, concept_name, (center_x-5, center_y-10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
                        elif concept_name in ["goal_line"]:
                            color = (0, 255, 255)  # Yellow for goal line
                            cv2.rectangle(vis_frame, (x1, y1), (x2, y2), color, 2)
                        elif concept_name in ["inner", "low_edge", "up_edge"]:
                            color = (255, 255, 0)  # Cyan for hash marks
                            points = np.array([
                                [center_x, y1],
                                [x2, center_y],
                                [center_x, y2],
                                [x1, center_y]
                            ], np.int32)
                            cv2.polylines(vis_frame, [points], True, color, 3)
                        
                    except Exception as e:
                        continue

                # Draw visualizations on both frames
                # 2. Draw player positions and tracks on the field view
                for player_id, track in self.player_tracks.items():
                    if not track['positions']:
                        continue
                        
                    color = self.get_player_color(player_id)
                    
                    # Draw track line with interpolated positions
                    positions = track['positions']
                    
                    # Add interpolated positions if available
                    if player_id in self.interpolated_positions:
                        interpolated = self.interpolated_positions[player_id]
                        # Combine interpolated positions with actual positions
                        all_positions = positions + interpolated
                    else:
                        all_positions = positions
                    
                    # Draw smooth track line
                    if len(all_positions) > 1:
                        for i in range(1, len(all_positions)):
                            pt1 = all_positions[i-1]
                            pt2 = all_positions[i]
                            cv2.line(field_view, pt1, pt2, color, 2)
                    
                    # Draw current position (use smoothed position if available)
                    if positions:
                        current_pos = positions[-1]
                        # draw a black circle instead of white
                        cv2.circle(field_view, current_pos, 5, (0, 0, 0), -1)
                        cv2.circle(field_view, current_pos, 4, color, -1)
                        
                        # Draw velocity vector if available
                        if 'velocity' in track and track['velocity'] != (0, 0):
                            vx, vy = track['velocity']
                            # Scale velocity for visualization
                            scale = 3.0
                            end_x = int(current_pos[0] + vx * scale)
                            end_y = int(current_pos[1] + vy * scale)
                            cv2.arrowedLine(field_view, current_pos, (end_x, end_y), color, 2)
                    
                    #cv2.putText(field_view, str(player_id), 
                    #           (current_pos[0]+5, current_pos[1]+5),
                    #           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                
                # IMPORTANT: Draw camera motion tracking keypoints on top of player visualization
                # This ensures both player detections and keypoints are visible simultaneously
                if hasattr(self, 'prev_keypoints') and self.prev_keypoints is not None and len(self.prev_keypoints) > 0:
                    # Always draw keypoints on the visualization frame
                    num_points = len(self.prev_keypoints)
                    for i in range(num_points):
                        pt = self.prev_keypoints[i][0]
                        # Draw yellow circles for keypoints - will be visible on top of player masks
                        cv2.circle(vis_frame, (int(pt[0]), int(pt[1])), 3, (0, 255, 255), -1)
                    
                    # Add keypoint count text
                    cv2.putText(vis_frame, f"Keypoints: {num_points}", 
                               (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                # Store current positions for next frame
                last_positions = current_positions.copy()
                
                # Write frames to video
                out_original.write(vis_frame)
                out_field.write(field_view)
                
                # Log progress
                if frame_count % 10 == 0:
                    print(f"Processed frame {frame_count} (actual: {actual_frame_count}/{total_frames}) - Tracking {len(self.player_tracks)} players")
                
                # Update UI with latest frames
                # Convert frames to format suitable for Tkinter
                vis_frame_rgb = cv2.cvtColor(vis_frame, cv2.COLOR_BGR2RGB)
                vis_img = Image.fromarray(vis_frame_rgb)
                vis_img = vis_img.resize((int(self.width * 0.8), int(self.height * 0.8)))
                
                field_view_rgb = cv2.cvtColor(field_view, cv2.COLOR_BGR2RGB)
                field_pil = Image.fromarray(field_view_rgb)
                
                # Create and store new PhotoImage objects
                self.tk_img = ImageTk.PhotoImage(image=vis_img)
                self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
                
                # Update canvas items with new images
                self.canvas.itemconfig(self.canvas_img, image=self.tk_img)
                self.field_canvas.itemconfig(self.field_canvas_img, image=self.field_tk_img)
                
                # Force UI update after each frame to show real-time progress
                self.root.update_idletasks()  # First process all idle tasks
                self.root.update()           # Then update the UI
                
                # Add a short sleep to allow the UI to catch up if needed
                # Only if we're processing frames very quickly
                current_time = time.time()
                elapsed = current_time - last_ui_update_time
                if elapsed < 0.05:  # If processing faster than 20fps
                    time.sleep(0.05 - elapsed)  # Sleep just enough to maintain ~20fps UI updates
                last_ui_update_time = time.time()

                # Periodically recompute homography using accumulated keypoints
                if frame_count - last_homography_recompute >= HOMOGRAPHY_RECOMPUTE_INTERVAL:
                    try:
                        print(f"Recomputing homography at frame {frame_count}")
                        
                        # Collect recent keypoints
                        if len(keypoint_history) >= 4:  # Need at least 4 points for homography
                            # Convert keypoints to numpy arrays
                            src_pts = np.array([kp[0] for kp in keypoint_history], dtype=np.float32)
                            
                            # Transform these points to field coordinates using current homography
                            dst_pts = cv2.perspectiveTransform(
                                src_pts.reshape(-1, 1, 2), 
                                self.homography_matrix
                            ).reshape(-1, 2)
                            
                            # Compute new homography with more aggressive parameters
                            new_homography, mask = cv2.findHomography(
                                src_pts,
                                dst_pts,
                                method=cv2.RANSAC,
                                ransacReprojThreshold=3.0,  # Reduced from 5.0 for tighter matching
                                maxIters=5000,  # Increased from 2000 for more thorough computation
                                confidence=0.999  # Increased from 0.995 for more reliable results
                            )
                            
                            if new_homography is not None and not np.isnan(new_homography).any():
                                # Blend the new homography with the current one
                                # Use a higher blend factor for more aggressive updates
                                blend_factor = 0.5  # Increased from 0.3
                                self.homography_matrix = (1 - blend_factor) * self.homography_matrix + blend_factor * new_homography
                                
                                # Normalize the homography matrix
                                if self.homography_matrix[2, 2] != 0:
                                    self.homography_matrix = self.homography_matrix / self.homography_matrix[2, 2]
                                
                                print(f"Homography successfully updated with {len(src_pts)} keypoints")
                            else:
                                print("Warning: Failed to compute new homography")
                        
                        # Don't clear keypoint history after recomputation
                        # Only remove oldest points if we exceed MAX_KEYPOINT_HISTORY
                        if len(keypoint_history) > MAX_KEYPOINT_HISTORY:
                            keypoint_history = keypoint_history[-MAX_KEYPOINT_HISTORY:]
                            
                        last_homography_recompute = frame_count
                        
                    except Exception as e:
                        print(f"Error recomputing homography: {str(e)}")
                
                # Store current keypoints for future homography recomputation
                if hasattr(self, 'prev_keypoints') and self.prev_keypoints is not None:
                    # Add all current keypoints to history
                    keypoint_history.extend(self.prev_keypoints)
                    # Only trim if we exceed the maximum
                    if len(keypoint_history) > MAX_KEYPOINT_HISTORY:
                        keypoint_history = keypoint_history[-MAX_KEYPOINT_HISTORY:]

            # Cleanup
            cap.release()
            out_original.release()
            out_field.release()
            progress_frame.destroy()
            
            # Display appropriate message based on how processing ended
            if self.stop_processing:
                processed_percent = (actual_frame_count / total_frames) * 100
                message = f"Video processing stopped at {frame_count} frames ({processed_percent:.1f}% complete)."
                print(message)
                print(f"Partial results saved to {output_original_path} and {output_field_path}")
            else:
                print("Video processing complete!")
                self.instruction_label.config(text=f"Video processing complete! Processed {frame_count} frames. Check output_original.mp4 and output_field.mp4")
            
            # Save player tracking data to CSV
            import csv
            import os
            from datetime import datetime
            
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(output_original_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Generate timestamp for unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = os.path.join(output_dir, f"player_tracking_{timestamp}.csv")
            
            # Write tracking data to CSV
            with open(csv_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                writer.writerow(['frame', 'player_id', 'x', 'y', 'speed', 'velocity_x', 'velocity_y'])
                
                # Write data for each frame
                for frame_idx, frame_data in enumerate(self.tracking_history):
                    for track in frame_data:
                        writer.writerow([
                            frame_idx,
                            track['id'],
                            track['x'],
                            track['y'],
                            track.get('speed', 0),
                            track.get('velocity_x', 0),
                            track.get('velocity_y', 0)
                        ])
            
            print(f"Player tracking data saved to {csv_path}")
            
            # Reset stop flag
            self.stop_processing = False

            # Add field of view visualization
            field_of_view_frame = self.field_img.copy()
            
            # Draw field of view boundary if we have enough points
            if len(self.field_of_view_points) >= 3:
                # Convert points to numpy array for drawing
                fov_points = np.array(self.field_of_view_points, dtype=np.int32)
                
                # Draw the field of view boundary
                cv2.polylines(field_of_view_frame, [fov_points], True, (0, 255, 255), 2)
                
                # Add to history for smoothing
                self.field_of_view_history.append(fov_points)
                if len(self.field_of_view_history) > self.max_fov_history:
                    self.field_of_view_history.pop(0)
                
                # If we have history, draw a smoothed boundary
                if len(self.field_of_view_history) > 1:
                    # Average the points from history
                    smoothed_points = np.mean(self.field_of_view_history, axis=0).astype(np.int32)
                    cv2.polylines(field_of_view_frame, [smoothed_points], True, (0, 200, 255), 1)
            
            # Update the field view with field of view visualization
            field_view_rgb = cv2.cvtColor(field_of_view_frame, cv2.COLOR_BGR2RGB)
            field_pil = Image.fromarray(field_view_rgb)
            self.field_tk_img = ImageTk.PhotoImage(image=field_pil)
            self.field_canvas.itemconfig(self.field_canvas_img, image=self.field_tk_img)

            try:
                status_label.config(text="Video processing complete!")
                progress_label.config(text="100%")
                progress_bar['value'] = 100
                self.root.update()
            except Exception as e:
                print(f"Warning: Could not update UI elements: {str(e)}")
                # Continue with cleanup even if UI updates fail

            # Write tracking data to CSV
            if self.tracking_history:
                try:
                    # Create output directory if it doesn't exist
                    os.makedirs('output', exist_ok=True)
                    
                    # Generate timestamp for filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_filename = f'output/tracking_data_{timestamp}.csv'
                    
                    # Write CSV header
                    with open(csv_filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['frame', 'id', 'field_x', 'field_y', 'speed', 'velocity_x', 'velocity_y'])
                        
                        # Write data for each frame
                        for frame_idx, frame_data in enumerate(self.tracking_history):
                            for track in frame_data:
                                # Get the latest position from the track
                                if track['positions']:
                                    field_x, field_y = track['positions'][-1]
                                    writer.writerow([
                                        frame_idx,
                                        track['id'],
                                        field_x,
                                        field_y,
                                        track.get('speed', 0),
                                        track.get('velocity_x', 0),
                                        track.get('velocity_y', 0)
                                    ])
                    
                    try:
                        status_label.config(text=f"Video processing complete! Tracking data saved to {csv_filename}")
                    except Exception as e:
                        print(f"Warning: Could not update status label: {str(e)}")
                except Exception as e:
                    try:
                        status_label.config(text=f"Video processing complete! Error saving tracking data: {str(e)}")
                    except Exception as e2:
                        print(f"Warning: Could not update status label: {str(e2)}")
            
            # Clean up
        except Exception as e:
            print(f"Error in video processing: {str(e)}")
            import traceback
            traceback.print_exc()
            self.instruction_label.config(text=f"Error processing video: {str(e)}")
        finally:
            # Reset stop flag regardless of how processing ended
            self.stop_processing = False
            
            # Clean up resources
            if 'cap' in locals():
                cap.release()
            if 'out_original' in locals():
                out_original.release()
            if 'out_field' in locals():
                out_field.release()
            cv2.destroyAllWindows()

    def start_video_processing(self):
        """Start video processing in a separate thread to keep UI responsive"""
        import threading
        self.process_video_btn.config(state=tk.DISABLED)
        self.instruction_label.config(text="Processing video... This may take a while.")
        
        def process_thread():
            try:
                self.process_video()
                self.root.after(0, lambda: self.instruction_label.config(
                    text="Video processing complete! Check output_original.mp4 and output_field.mp4"))
            except Exception as e:
                self.root.after(0, lambda: self.instruction_label.config(
                    text=f"Error processing video: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.process_video_btn.config(state=tk.NORMAL))
        
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()

    def update_camera_motion(self, current_frame, keypoint_history=None):
        """Update homography matrix based on camera motion between frames using
        optical flow and dynamic keypoint selection that ignores players"""
        try:
            # Initialize tracking on first frame
            if self.prev_frame is None:
                self.prev_frame = current_frame.copy()
                # Convert to grayscale for feature detection
                gray_frame = cv2.cvtColor(self.prev_frame, cv2.COLOR_BGR2GRAY)
                
                # Create a mask to exclude player regions initially
                player_mask = np.ones_like(gray_frame, dtype=np.uint8) * 255
                
                # Get player detections from first frame
                _, img_encoded = cv2.imencode('.jpg', self.prev_frame)
                img_bytes = img_encoded.tobytes()
                
                try:
                    # Get player detections from Clarifai
                    results = self.model_player_ref.predict_by_bytes(img_bytes, input_type="image")
                    regions = results.outputs[0].data.regions
                    
                    # Mask out all detected players
                    for region in regions:
                        # Check if region has concepts and filter by them
                        should_process = True
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            try:
                                region_concepts = [c.name for c in region.data.concepts]
                                should_process = any(concept in region_concepts for concept in self.concepts_player_ref)
                                if not should_process:
                                    continue
                            except Exception as e:
                                print(f"Error checking concepts for region: {e}")
                                should_process = True
                        
                        # Get confidence ONLY from first concept
                        conf = 0.0
                        if hasattr(region, 'data') and hasattr(region.data, 'concepts'):
                            concepts_list = region.data.concepts
                            if concepts_list and hasattr(concepts_list[0], 'value'):
                                conf = concepts_list[0].value
                        
                        if conf < self.conf_threshold:
                            continue
                            
                        # Get bounding box
                        bbox = region.region_info.bounding_box
                        x1 = int(bbox.left_col * self.width)
                        y1 = int(bbox.top_row * self.height)
                        x2 = int(bbox.right_col * self.width)
                        y2 = int(bbox.bottom_row * self.height)
                        
                        # Make player region black in mask (excluded from feature detection)
                        cv2.rectangle(player_mask, (x1, y1), (x2, y2), 0, -1)
                        
                        # Add some extra padding around player
                        padding = 10
                        x1_pad = max(0, x1 - padding)
                        y1_pad = max(0, y1 - padding)
                        x2_pad = min(self.width, x2 + padding)
                        y2_pad = min(self.height, y2 + padding)
                        cv2.rectangle(player_mask, (x1_pad, y1_pad), (x2_pad, y2_pad), 0, -1)
                        
                    print(f"Masked {len(regions)} players for initial keypoint detection")
                except Exception as e:
                    print(f"Warning: Could not detect players for masking: {e}")

                # Detect initial features in first frame (avoiding players)
                self.prev_keypoints = cv2.goodFeaturesToTrack(
                    gray_frame,
                    maxCorners=self.MAX_TRACKING_POINTS,
                    qualityLevel=0.02,  # Increased from 0.01 for better quality features
                    minDistance=15,
                    mask=player_mask,
                    blockSize=9
                )
                
                if self.prev_keypoints is None or len(self.prev_keypoints) < self.MIN_TRACKING_POINTS // 2:
                    print("Warning: Not enough features found in first frame")
                    return None, 0.0
                
                # Store previous frame info
                self.prev_gray = gray_frame
                print(f"Initial tracking: {len(self.prev_keypoints)} keypoints")
                
                # Initialize keypoint history if not provided
                if keypoint_history is None:
                    keypoint_history = []
                
                # Return identity matrix for first frame (no motion yet)
                return np.eye(3, 3, dtype=np.float32), 1.0
            
            # --- Subsequent frame processing ---
            current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
            
            # Ensure we have keypoints to track
            if self.prev_keypoints is None or len(self.prev_keypoints) < 10:
                 print("No valid keypoints to track, attempting re-detection.")
                 # Force re-detection by setting prev_keypoints to an empty array
                 self.prev_keypoints = np.empty((0, 1, 2), dtype=np.float32)
                 # Skip optical flow for this frame, proceed directly to re-detection check
                 good_new = np.empty((0, 2), dtype=np.float32)
                 good_old = np.empty((0, 2), dtype=np.float32)
                 transform_matrix = None
                 tracking_quality = 0.0
            else:
                # Calculate optical flow to track existing keypoints
                curr_keypoints, status, error = cv2.calcOpticalFlowPyrLK(
                    self.prev_gray, 
                    current_gray, 
                    self.prev_keypoints, 
                    None,
                    **self.optical_flow_params
                )
                
                # Filter out points lost in tracking
                if curr_keypoints is None or status is None:
                    print("Warning: Optical flow failed")
                    # Attempt re-detection if flow fails completely
                    self.prev_keypoints = np.empty((0, 1, 2), dtype=np.float32)
                    good_new = np.empty((0, 2), dtype=np.float32)
                    good_old = np.empty((0, 2), dtype=np.float32)
                    transform_matrix = None
                    tracking_quality = 0.0
                else:
                    # Select good points that were successfully tracked
                    valid_indices = (status == 1).flatten()
                    good_new = curr_keypoints[valid_indices]
                    good_old = self.prev_keypoints[valid_indices]
                    
                    # Need at least a few points for reliable homography
                    if len(good_new) < 10:
                        print(f"Warning: Very few points tracked ({len(good_new)}). Tracking may be lost.")
                        # Still attempt homography but quality will be low
                        if len(good_new) < 4: # Cannot compute homography
                             print("Fewer than 4 points tracked, cannot compute homography.")
                             self.prev_keypoints = np.empty((0, 1, 2), dtype=np.float32)
                             good_new = np.empty((0, 2), dtype=np.float32)
                             good_old = np.empty((0, 2), dtype=np.float32)
                             transform_matrix = None
                             tracking_quality = 0.0
                             # Proceed to re-detection check
                    
                    # Calculate homography between previous and current frame if enough points
                    transform_matrix = None
                    tracking_quality = 0.0
                    if len(good_new) >= 4:
                        try:
                            transform_matrix, h_mask = cv2.findHomography(
                                good_old, 
                                good_new, 
                                cv2.RANSAC,
                                self.adaptive_ransac_threshold,
                                maxIters=2000,
                                confidence=0.995
                            )
                            
                            if transform_matrix is None or np.isnan(transform_matrix).any():
                                print("Warning: Invalid homography matrix computed")
                                transform_matrix = None
                                tracking_quality = 0.0
                                # Keep only optically tracked points if homography fails
                                self.prev_keypoints = good_new.reshape(-1, 1, 2)
                            else:
                                # Homography succeeded, filter points by RANSAC mask
                                inliers = np.sum(h_mask)
                                total_points = len(good_old)
                                inlier_ratio = inliers / total_points if total_points > 0 else 0
                                tracking_quality = inlier_ratio
                                print(f"Homography: {inliers}/{total_points} inliers ({tracking_quality:.2f})")

                                if tracking_quality < 0.4:
                                    print("Warning: Low inlier ratio, homography might be unreliable")
                                
                                # Update tracked points to only include RANSAC inliers
                                self.prev_keypoints = good_new[h_mask.ravel() == 1].reshape(-1, 1, 2)
                                
                                # Normalize the homography matrix
                                if transform_matrix[2, 2] != 0:
                                    transform_matrix = transform_matrix / transform_matrix[2, 2]

                                # Check for reasonable motion limits
                                tx = transform_matrix[0, 2]
                                ty = transform_matrix[1, 2]
                                max_translation = 150.0 # Increased limit slightly
                                if abs(tx) > max_translation or abs(ty) > max_translation:
                                    print(f"Warning: Excessive translation detected: {tx:.1f}, {ty:.1f}. Clamping quality.")
                                    tracking_quality = min(tracking_quality, 0.3) # Reduce quality score significantly
                                    # Consider resetting matrix? For now, just lower quality.
                                    # transform_matrix = None # Option: discard extreme motion

                        except Exception as e:
                            print(f"Error computing homography: {str(e)}")
                            transform_matrix = None
                            tracking_quality = 0.0
                            # Keep optically tracked points if homography crashes
                            self.prev_keypoints = good_new.reshape(-1, 1, 2)
                    else:
                         # Not enough points for homography after optical flow
                         self.prev_keypoints = good_new.reshape(-1, 1, 2) # Keep the few tracked points
                         transform_matrix = None
                         tracking_quality = 0.0


            # --- Dynamic Keypoint Re-detection ---
            num_current_points = len(self.prev_keypoints) if self.prev_keypoints is not None else 0
            
            if num_current_points < self.MIN_TRACKING_POINTS:
                print(f"Keypoints ({num_current_points}) below threshold ({self.MIN_TRACKING_POINTS}). Detecting new features.")
                
                # Create mask to avoid detecting near existing points and players
                combined_mask = np.ones_like(current_gray) * 255
                
                # 1. Mask out player regions (using mask from process_video if available)
                if self.player_mask is not None and self.player_mask.shape == combined_mask.shape:
                    combined_mask = cv2.bitwise_and(combined_mask, self.player_mask)
                else:
                    print("Warning: Player mask not available or mismatched shape for re-detection.")

                # 2. Mask out regions around existing keypoints with dynamic radius
                if self.prev_keypoints is not None:
                    # Adjust mask radius based on current point count
                    mask_radius = max(10, int(20 * (1 - num_current_points / self.MIN_TRACKING_POINTS)))
                    for pt in self.prev_keypoints:
                        x, y = map(int, pt[0])
                        cv2.circle(combined_mask, (x, y), radius=mask_radius, color=0, thickness=-1)
                
                # Detect new features in unmasked areas with adaptive parameters
                num_new_to_find = min(
                    self.MAX_TRACKING_POINTS - num_current_points,
                    int(self.MAX_TRACKING_POINTS * 0.5)  # Don't add too many at once
                )
                
                # Adjust quality level based on how many points we need
                quality_level = 0.02 if num_current_points > self.MIN_TRACKING_POINTS // 2 else 0.01
                
                new_features = cv2.goodFeaturesToTrack(
                    current_gray,
                    maxCorners=num_new_to_find,
                    qualityLevel=quality_level,
                    minDistance=15,
                    mask=combined_mask,
                    blockSize=9
                )
                
                if new_features is not None and len(new_features) > 0:
                    print(f"Detected {len(new_features)} new keypoints.")
                    # Append new features to existing ones
                    if self.prev_keypoints is not None and len(self.prev_keypoints) > 0:
                        self.prev_keypoints = np.vstack((self.prev_keypoints, new_features))
                    else:
                        self.prev_keypoints = new_features
                        
                    # Ensure we don't exceed max points
                    if len(self.prev_keypoints) > self.MAX_TRACKING_POINTS:
                        # Keep points with best response values
                        response = cv2.cornerHarris(current_gray, 2, 3, 0.04)
                        scores = [response[int(kp[0][1]), int(kp[0][0])] for kp in self.prev_keypoints]
                        idx = np.argsort(scores)[-self.MAX_TRACKING_POINTS:]
                        self.prev_keypoints = self.prev_keypoints[idx]
                        print(f"Trimmed to {len(self.prev_keypoints)} best keypoints")
                else:
                    print("No new features detected in this frame.")
            
            # Update previous frame info for the next iteration's optical flow
            self.prev_gray = current_gray
            self.prev_frame = current_frame.copy()

            # Return the inter-frame motion matrix and tracking quality
            return transform_matrix, tracking_quality
            
        except Exception as e:
            print(f"Error in update_camera_motion: {str(e)}")
            import traceback
            traceback.print_exc()
            # Reset state in case of error
            self.prev_frame = None
            self.prev_gray = None
            self.prev_keypoints = None
            return None, 0.0

    def get_player_color(self, player_id):
        """Generate a consistent color for a player ID using HSV color space"""
        hue = (player_id * 137.5) % 360  # Golden ratio * 360 for good distribution
        saturation = 0.75
        value = 0.9
        
        # Convert HSV to RGB
        h = hue / 360.0
        c = value * saturation
        x = c * (1 - abs((h * 6) % 2 - 1))
        m = value - c
        
        if h < 1/6:
            r, g, b = c, x, 0
        elif h < 2/6:
            r, g, b = x, c, 0
        elif h < 3/6:
            r, g, b = 0, c, x
        elif h < 4/6:
            r, g, b = 0, x, c
        elif h < 5/6:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
            
        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        
        return (b, g, r)  # OpenCV uses BGR format

    def apply_segmentation_mask(self, frame, bbox):
        """Apply SAM segmentation to get player mask"""
        try:
            # Convert frame to RGB for SAM
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.sam_predictor.set_image(frame_rgb)

            # Convert bbox to SAM input format [x, y, w, h]
            x1, y1, x2, y2 = bbox
            input_box = np.array([x1, y1, x2, y2])

            # Get SAM prediction
            masks, _, _ = self.sam_predictor.predict(
                point_coords=None,
                point_labels=None,
                box=input_box[None, :],
                multimask_output=False
            )

            return masks[0]  # Return first mask

        except Exception as e:
            print(f"Error in segmentation: {str(e)}")
            return None

    def apply_segmentation_masks_batch(self, frame, bboxes, detection_ids):
        """Apply segmentation efficiently to multiple boxes"""
        try:
            # If segmentation is not available, return empty masks immediately
            if not hasattr(self, 'segmentation_available') or not self.segmentation_available:
                print("Segmentation not available, skipping mask generation")
                return [None] * len(bboxes)
                
            if not bboxes:
                return []
                
            # Convert frame to RGB for SAM
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Null check before using predictor
            if self.sam_predictor is None:
                print("Error: SAM predictor is not initialized")
                return [None] * len(bboxes)
                
            # Use standard predictor
            masks = []
            
            # Set the image first
            self.sam_predictor.set_image(frame_rgb)
            
            # Process each box individually with improved bbox handling
            for bbox in bboxes:
                x1, y1, x2, y2 = bbox
                
                # Add padding to bbox for better segmentation
                padding = 10
                x1_pad = max(0, x1 - padding)
                y1_pad = max(0, y1 - padding)
                x2_pad = min(self.width, x2 + padding)
                y2_pad = min(self.height, y2 + padding)
                
                input_box = np.array([x1_pad, y1_pad, x2_pad, y2_pad])
                
                # Get SAM prediction with improved parameters
                mask_outputs, _, _ = self.sam_predictor.predict(
                    point_coords=None,
                    point_labels=None,
                    box=input_box[None, :],
                    multimask_output=False
                )
                
                # Post-process mask to ensure it's within original bbox
                mask = mask_outputs[0]
                h, w = mask.shape
                mask_bbox = np.zeros_like(mask)
                mask_bbox[y1:y2, x1:x2] = 1
                mask = np.logical_and(mask, mask_bbox)
                
                masks.append(mask)
            
            return masks
            
        except Exception as e:
            print(f"Error in batch segmentation: {e}")
            import traceback
            traceback.print_exc()
            return [None] * len(bboxes)

    def update_player_tracks(self, current_positions):
        """Update player tracks with new positions, including speed calculation"""
        if not self.player_tracks:
            # Initialize tracks for all players in first frame
            for pos in current_positions:
                x, y = pos
                pos_tuple = (int(float(x)), int(float(y)))
                self.player_tracks[self.next_player_id] = {
                    'positions': [pos_tuple],
                    'last_seen': 0,
                    'velocity': (0, 0),
                    'locked': False,
                    'lock_frames': 0,
                    'speed': 0.0,  # Speed in yards per second
                    'speed_history': []  # Store recent speeds
                }
                self.next_player_id += 1
                print(f"Created new track {self.next_player_id-1}, now tracking {len(self.player_tracks)} players")
            return

        # First, merge nearby detections that are likely the same player
        merged_positions = []
        used_indices = set()
        
        for i, pos1 in enumerate(current_positions):
            if i in used_indices:
                continue
                
            x1, y1 = pos1
            pos1_tuple = (int(float(x1)), int(float(y1)))
            
            # Find nearby detections with similar movement patterns
            nearby_detections = [pos1_tuple]
            nearby_indices = [i]
            
            for j, pos2 in enumerate(current_positions):
                if j <= i or j in used_indices:
                    continue
                    
                x2, y2 = pos2
                pos2_tuple = (int(float(x2)), int(float(y2)))
                
                # Calculate distance between detections
                dist = np.linalg.norm(np.array(pos1_tuple) - np.array(pos2_tuple))
                
                # If detections are very close, check if they have similar movement
                if dist < 15:  # Reduced from 25 - much more conservative
                    # Check if these detections have similar movement patterns
                    similar_movement = True
                    
                    # If we have existing tracks, check if both positions would match to the same track
                    if self.player_tracks:
                        # Find which track each position would match to
                        track1_id = None
                        track2_id = None
                        min_dist1 = float('inf')
                        min_dist2 = float('inf')
                        
                        for track_id, track in self.player_tracks.items():
                            if track['positions']:
                                last_pos = track['positions'][-1]
                                
                                # Calculate distance to each position
                                dist1 = np.linalg.norm(np.array(last_pos) - np.array(pos1_tuple))
                                dist2 = np.linalg.norm(np.array(last_pos) - np.array(pos2_tuple))
                                
                                # Track the closest match for each position
                                if dist1 < min_dist1:
                                    min_dist1 = dist1
                                    track1_id = track_id
                                if dist2 < min_dist2:
                                    min_dist2 = dist2
                                    track2_id = track_id
                        
                        # Only merge if both positions would match to the SAME track AND are very close
                        if track1_id == track2_id and track1_id is not None and dist < 10:  # Much stricter condition
                            # Additional check: if the track has velocity, check if both positions are consistent
                            track = self.player_tracks[track1_id]
                            if 'velocity' in track and track['velocity'] != (0, 0):
                                vx, vy = track['velocity']
                                # Predict where the player should be based on velocity
                                predicted_pos = (last_pos[0] + vx, last_pos[1] + vy)
                                
                                # Calculate distance from each detection to predicted position
                                dist_to_pred1 = np.linalg.norm(np.array(predicted_pos) - np.array(pos1_tuple))
                                dist_to_pred2 = np.linalg.norm(np.array(predicted_pos) - np.array(pos2_tuple))
                                
                                # If both detections are close to the predicted position, they're likely the same player
                                if dist_to_pred1 < 15 and dist_to_pred2 < 15:  # Reduced from 30
                                    similar_movement = True
                                else:
                                    similar_movement = False
                            else:
                                similar_movement = True  # No velocity info, assume same player
                        else:
                            # Different tracks or no match, don't merge
                            similar_movement = False
                    else:
                        # No existing tracks, only merge if very close
                        similar_movement = dist < 8  # Much stricter for new tracks
                    
                    if similar_movement:
                        nearby_detections.append(pos2_tuple)
                        nearby_indices.append(j)
                        used_indices.add(j)
                        print(f"Found nearby detections with similar movement: dist={dist:.1f}")
            
            # Average the nearby detections to get a single position
            if len(nearby_detections) > 1:
                avg_x = sum(pos[0] for pos in nearby_detections) / len(nearby_detections)
                avg_y = sum(pos[1] for pos in nearby_detections) / len(nearby_detections)
                merged_positions.append((int(avg_x), int(avg_y)))
                print(f"Merged {len(nearby_detections)} nearby detections (likely same player) into single position")
                
                # Also merge any existing tracks that correspond to these positions
                # DISABLED: This was causing incorrect track merging
                # self.merge_tracks_for_positions(nearby_detections)
            else:
                merged_positions.append(pos1_tuple)
            
            used_indices.add(i)
        
        # Use merged positions for tracking
        current_positions = merged_positions
        
        # Match current positions to existing tracks using greedy assignment
        matched_tracks = set()
        matched_positions = set()
        
        # Create distance matrix for all track-position pairs
        track_ids = list(self.player_tracks.keys())
        position_indices = list(range(len(current_positions)))
        
        # Calculate all distances
        distances = []
        for track_id in track_ids:
            track = self.player_tracks[track_id]
            if track.get('locked', False):
                track['lock_frames'] -= 1
                if track['lock_frames'] <= 0:
                    track['locked'] = False
                continue
                
            last_pos = track['positions'][-1]
            
            # Calculate predicted position
            predicted_pos = last_pos
            if 'velocity' in track and track['velocity'] != (0, 0):
                vx, vy = track['velocity']
                predicted_pos = (last_pos[0] + vx, last_pos[1] + vy)
            
            for pos_idx, pos in enumerate(current_positions):
                x, y = pos
                pos_tuple = (int(float(x)), int(float(y)))
                
                # Calculate distance to predicted position
                dist = np.linalg.norm(np.array(predicted_pos) - np.array(pos_tuple))
                
                # Calculate adaptive max distance - much more conservative
                base_max_dist = 15  # Reduced from 25
                velocity_factor = min(1.2, max(0.8, (abs(track.get('velocity', (0, 0))[0]) + abs(track.get('velocity', (0, 0))[1])) / 10))  # Reduced from 15
                age_factor = min(1.1, max(0.9, len(track['positions']) / 20))  # Reduced from 15
                max_dist = min(base_max_dist * velocity_factor * age_factor, 25)  # Reduced from 40
                
                if dist <= max_dist:
                    distances.append((track_id, pos_idx, dist))
        
        # Sort by distance and assign greedily
        distances.sort(key=lambda x: x[2])
        for track_id, pos_idx, dist in distances:
            if track_id not in matched_tracks and pos_idx not in matched_positions:
                # Match this track to this position
                track = self.player_tracks[track_id]
                pos = current_positions[pos_idx]
                x, y = pos
                pos_tuple = (int(float(x)), int(float(y)))
                
                # Calculate velocity
                if len(track['positions']) > 0:
                    last_pos = track['positions'][-1]
                    vx = pos_tuple[0] - last_pos[0]
                    vy = pos_tuple[1] - last_pos[1]
                    
                    # Check if the movement is reasonable (not too large)
                    movement_distance = np.sqrt(vx**2 + vy**2)
                    if movement_distance > 30:  # Reduced from 50 - more conservative
                        print(f"Skipping track {track_id} update - movement too large: {movement_distance:.1f}")
                        continue
                    
                    track['velocity'] = (vx, vy)
                
                # Apply smoothing
                if len(track['positions']) > 0:
                    smoothed_pos = (
                        int(last_pos[0] * (1 - self.smoothing_factor) + pos_tuple[0] * self.smoothing_factor),
                        int(last_pos[1] * (1 - self.smoothing_factor) + pos_tuple[1] * self.smoothing_factor)
                    )
                    track['positions'].append(smoothed_pos)
                else:
                    track['positions'].append(pos_tuple)
                
                track['last_seen'] = 0
                matched_tracks.add(track_id)
                matched_positions.add(pos_idx)
                
                if dist > 15:  # Reduced from 20 - more conservative logging
                    print(f"High distance match: Track {track_id} -> Position {pos_idx}, dist={dist:.1f}")
        
        # Handle unmatched tracks
        for track_id, track in self.player_tracks.items():
            if track_id not in matched_tracks:
                track['last_seen'] += 1
                if track['last_seen'] > 60 and not track.get('locked', False):
                    track['locked'] = True
                    track['lock_frames'] = 10

        # Create new tracks for unmatched positions, but be more conservative
        for pos_idx, pos in enumerate(current_positions):
            if pos_idx not in matched_positions:
                # Check if this position is too close to any existing track
                x, y = pos
                pos_tuple = (int(float(x)), int(float(y)))
                
                # Only create new track if it's not too close to existing tracks
                too_close = False
                for track_id, track in self.player_tracks.items():
                    if track['positions']:
                        last_pos = track['positions'][-1]
                        dist = np.linalg.norm(np.array(last_pos) - np.array(pos_tuple))
                        if dist < 10:  # Reduced from 15 - more conservative new track creation
                            too_close = True
                            break
                
                if not too_close:
                    # STRICT LIMIT: Never create more than 22 tracks
                    if len(self.player_tracks) >= 22:
                        print(f"STRICT LIMIT: Already tracking {len(self.player_tracks)} players, skipping new track creation")
                        continue
                    
                self.player_tracks[self.next_player_id] = {
                    'positions': [pos_tuple],
                    'last_seen': 0,
                    'velocity': (0, 0),
                    'locked': False,
                        'lock_frames': 0,
                        'speed': 0.0,
                        'speed_history': []
                }
                self.next_player_id += 1
                print(f"Created new track {self.next_player_id-1}, now tracking {len(self.player_tracks)} players")

        # Remove tracks that haven't been seen for too long
        self.player_tracks = {track_id: track for track_id, track in self.player_tracks.items() 
                            if track['last_seen'] <= self.track_history_length}

        # AGGRESSIVE MERGING: If we have more than 22 tracks, merge the closest ones
        if len(self.player_tracks) > 22:
            print(f"AGGRESSIVE MERGING: {len(self.player_tracks)} tracks detected, merging duplicates...")
            
            # Find tracks that are very close to each other with similar movement
            tracks_to_merge = []
            track_ids = list(self.player_tracks.keys())
            
            for i, track_id1 in enumerate(track_ids):
                for j, track_id2 in enumerate(track_ids[i+1:], i+1):
                    track1 = self.player_tracks[track_id1]
                    track2 = self.player_tracks[track_id2]
                    
                    if track1['positions'] and track2['positions']:
                        pos1 = track1['positions'][-1]
                        pos2 = track2['positions'][-1]
                        dist = np.linalg.norm(np.array(pos1) - np.array(pos2))
                        
                        # If tracks are very close, check if they have similar movement patterns
                        if dist < 12:  # Reduced from 25 - much more conservative
                            similar_movement = True
                            
                            # Check if both tracks have similar velocity patterns
                            if 'velocity' in track1 and 'velocity' in track2:
                                v1 = track1['velocity']
                                v2 = track2['velocity']
                                
                                # Calculate velocity similarity
                                if v1 != (0, 0) and v2 != (0, 0):
                                    # Normalize velocities and calculate similarity
                                    mag1 = np.sqrt(v1[0]**2 + v1[1]**2)
                                    mag2 = np.sqrt(v2[0]**2 + v2[1]**2)
                                    
                                    if mag1 > 0 and mag2 > 0:
                                        # Normalize and compare directions
                                        v1_norm = (v1[0]/mag1, v1[1]/mag1)
                                        v2_norm = (v2[0]/mag2, v2[1]/mag2)
                                        
                                        # Calculate dot product (similarity)
                                        dot_product = v1_norm[0]*v2_norm[0] + v1_norm[1]*v2_norm[1]
                                        
                                        # If velocities are very different (>90 degrees apart), don't merge
                                        if dot_product < 0:  # Opposite directions
                                            similar_movement = False
                                            print(f"Tracks {track_id1} and {track_id2} have opposite movement, not merging")
                                        elif dot_product < 0.7:  # Increased from 0.5 - more strict
                                            similar_movement = False
                                            print(f"Tracks {track_id1} and {track_id2} have different movement patterns, not merging")
                                        else:
                                            print(f"Tracks {track_id1} and {track_id2} have similar movement (dot={dot_product:.2f})")
                            
                            # If movement patterns are similar, mark for merging
                            if similar_movement:
                                tracks_to_merge.append((track_id1, track_id2, dist))
                                print(f"Marking tracks {track_id1} and {track_id2} for merging (dist={dist:.1f}, similar movement)")
            
            # Sort by distance and merge closest pairs first
            tracks_to_merge.sort(key=lambda x: x[2])
            
            # Merge tracks, keeping the one with more history
            merged_tracks = set()
            for track_id1, track_id2, dist in tracks_to_merge:
                if track_id1 not in merged_tracks and track_id2 not in merged_tracks:
                    track1 = self.player_tracks[track_id1]
                    track2 = self.player_tracks[track_id2]
                    
                    # Keep the track with more history and better velocity data
                    score1 = len(track1['positions']) + (10 if 'velocity' in track1 and track1['velocity'] != (0, 0) else 0)
                    score2 = len(track2['positions']) + (10 if 'velocity' in track2 and track2['velocity'] != (0, 0) else 0)
                    
                    if score1 >= score2:
                        track_to_keep = track_id1
                        track_to_remove = track_id2
                    else:
                        track_to_keep = track_id2
                        track_to_remove = track_id1
                    
                    print(f"Merging tracks {track_id1} and {track_id2} (dist={dist:.1f}), keeping {track_to_keep}")
                    del self.player_tracks[track_to_remove]
                    merged_tracks.add(track_to_remove)
                    
                    # Stop if we're down to 22 or fewer tracks
                    if len(self.player_tracks) <= 22:
                        break
            
            print(f"After merging: {len(self.player_tracks)} tracks")
            
            # If still over 22, remove oldest tracks
            if len(self.player_tracks) > 22:
                print(f"Still {len(self.player_tracks)} tracks, removing oldest...")
                # Sort tracks by last_seen (oldest first)
                sorted_tracks = sorted(self.player_tracks.items(), key=lambda x: x[1]['last_seen'], reverse=True)
                
                # Remove oldest tracks until we're at 22
                tracks_to_remove = len(self.player_tracks) - 22
                for i in range(tracks_to_remove):
                    track_id = sorted_tracks[i][0]
                    print(f"Removing old track {track_id} (last_seen={self.player_tracks[track_id]['last_seen']})")
                    del self.player_tracks[track_id]
                
                print(f"After removing oldest: {len(self.player_tracks)} tracks")

        # Periodic cleanup of old tracks (every 30 frames)
        if hasattr(self, 'frame_count_for_cleanup'):
            self.frame_count_for_cleanup += 1
        else:
            self.frame_count_for_cleanup = 0
        
        if self.frame_count_for_cleanup >= 30:
            self.frame_count_for_cleanup = 0
            
            # Remove tracks that haven't been seen for a long time
            old_tracks = []
            for track_id, track in self.player_tracks.items():
                if track['last_seen'] > 60:  # Reduced from 120 - more aggressive cleanup
                    old_tracks.append(track_id)
            
            for track_id in old_tracks:
                print(f"Removing old track {track_id} (not seen for {self.player_tracks[track_id]['last_seen']} frames)")
                del self.player_tracks[track_id]
            
            if old_tracks:
                print(f"Removed {len(old_tracks)} old tracks, now tracking {len(self.player_tracks)} players")
        
        # FINAL ENFORCEMENT: If somehow we still have more than 22 tracks, force removal
        if len(self.player_tracks) > 22:
            print(f"FINAL ENFORCEMENT: {len(self.player_tracks)} tracks, forcing removal of oldest...")
            # Sort by last_seen and remove oldest
            sorted_tracks = sorted(self.player_tracks.items(), key=lambda x: x[1]['last_seen'], reverse=True)
            tracks_to_remove = len(self.player_tracks) - 22
            
            for i in range(tracks_to_remove):
                track_id = sorted_tracks[i][0]
                print(f"FORCED REMOVAL: Track {track_id} (last_seen={self.player_tracks[track_id]['last_seen']})")
                del self.player_tracks[track_id]
            
            print(f"After forced removal: {len(self.player_tracks)} tracks")
        
        # After updating positions, calculate speeds if reference segment is set
        if self.reference_complete and self.pixels_per_yard is not None and hasattr(self, 'video_fps'):
            for track_id, track in self.player_tracks.items():
                if len(track['positions']) >= 2:
                    # Use last 5 positions for speed calculation
                    num_frames = min(5, len(track['positions']))
                    positions = track['positions'][-num_frames:]
                    
                    # Calculate total distance over the frames
                    total_distance_pixels = 0
                    for i in range(1, len(positions)):
                        pos1 = positions[i-1]
                        pos2 = positions[i]
                        total_distance_pixels += np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
                    
                    # Convert to yards using our reference
                    total_distance_yards = total_distance_pixels / self.pixels_per_yard
                    
                    # Calculate average speed in yards per second
                    # Divide by (num_frames-1) because we have (num_frames-1) segments
                    avg_speed_yps = (total_distance_yards * self.video_fps) / (num_frames-1)
                    
                    # Convert to miles per hour (1 yard/second = 2.04545 mph)
                    speed_mph = avg_speed_yps * 2.04545
                    
                    # Initialize speed_history if it doesn't exist
                    if 'speed_history' not in track:
                        track['speed_history'] = []
                    
                    # Update track speed
                    track['speed'] = speed_mph
                    track['speed_history'].append(speed_mph)
                    
                    # Keep only recent speed history
                    if len(track['speed_history']) > 10:
                        track['speed_history'].pop(0)

    def draw_tracks_on_field(self, field_view):
        """Draw player tracks on the field view"""
        for player_id, track in self.player_tracks.items():
            if len(track['positions']) < 2:
                continue

            color = self.get_player_color(player_id)
            
            # Draw track path
            for i in range(1, len(track['positions'])):
                try:
                    # Get positions (already stored as Python integer tuples)
                    pt1 = track['positions'][i-1]
                    pt2 = track['positions'][i]
                    
                    # Ensure points are within bounds
                    height, width = field_view.shape[:2]
                    pt1 = (max(0, min(pt1[0], width-1)), max(0, min(pt1[1], height-1)))
                    pt2 = (max(0, min(pt2[0], width-1)), max(0, min(pt2[1], height-1)))
                    
                    # Draw line between points
                    cv2.line(field_view, pt1, pt2, color, 2)
                except Exception as e:
                    print(f"Error drawing line for player {player_id}: {e}")
                    continue

            # Draw current position and speed
            if track['positions']:
                try:
                    # Get current position (already stored as Python integer tuple)
                    pos = track['positions'][-1]
                    
                    # Ensure point is within bounds
                    height, width = field_view.shape[:2]
                    pos = (max(0, min(pos[0], width-1)), max(0, min(pos[1], height-1)))
                    
                    cv2.circle(field_view, pos, 4, color, -1)
                    cv2.putText(field_view, str(player_id), 
                               (pos[0]-3, pos[1]-5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
                except Exception as e:
                    print(f"Error drawing position for player {player_id}: {e}")
                    continue

    def merge_corresponding_tracks(self, detections):
        """Merge tracks that correspond to the same player based on detection positions"""
        if not self.player_tracks or len(detections) < 2:
            return
        
        # Get foot positions from detections
        detection_positions = [det['foot'] for det in detections]
        
        # Find tracks that are close to these detection positions
        tracks_to_merge = []
        
        for track_id, track in self.player_tracks.items():
            if track['positions']:
                last_pos = track['positions'][-1]
                
                # Check if this track is close to any of the detection positions
                for det_pos in detection_positions:
                    dist = np.sqrt((last_pos[0] - det_pos[0])**2 + (last_pos[1] - det_pos[1])**2)
                    if dist < 20:  # Reduced from 40 - much more conservative
                        tracks_to_merge.append(track_id)
                        break
        
        # If we found multiple tracks for the same player, merge them
        if len(tracks_to_merge) > 1:
            print(f"Merging {len(tracks_to_merge)} tracks for same player: {tracks_to_merge}")
            
            # Keep the track with the most history
            best_track_id = None
            max_history = 0
            
            for track_id in tracks_to_merge:
                track = self.player_tracks[track_id]
                if len(track['positions']) > max_history:
                    max_history = len(track['positions'])
                    best_track_id = track_id
            
            # Merge all other tracks into the best one
            for track_id in tracks_to_merge:
                if track_id != best_track_id:
                    track_to_merge = self.player_tracks[track_id]
                    best_track = self.player_tracks[best_track_id]
                    
                    # Merge position histories (interleave them chronologically if possible)
                    # For now, just append the positions from the track being merged
                    if track_to_merge['positions']:
                        best_track['positions'].extend(track_to_merge['positions'])
                        
                        # Sort positions by some criteria (could be improved with timestamps)
                        # For now, just keep the most recent positions
                        if len(best_track['positions']) > self.track_history_length:
                            best_track['positions'] = best_track['positions'][-self.track_history_length:]
                    
                    # Merge velocity data if available
                    if 'velocity' in track_to_merge and track_to_merge['velocity'] != (0, 0):
                        if 'velocity' not in best_track or best_track['velocity'] == (0, 0):
                            best_track['velocity'] = track_to_merge['velocity']
                        else:
                            # Average the velocities
                            v1 = best_track['velocity']
                            v2 = track_to_merge['velocity']
                            best_track['velocity'] = ((v1[0] + v2[0])/2, (v1[1] + v2[1])/2)
                    
                    # Merge speed data
                    if 'speed' in track_to_merge:
                        if 'speed' not in best_track:
                            best_track['speed'] = track_to_merge['speed']
                        else:
                            best_track['speed'] = (best_track['speed'] + track_to_merge['speed']) / 2
                    
                    # Merge speed history
                    if 'speed_history' in track_to_merge:
                        if 'speed_history' not in best_track:
                            best_track['speed_history'] = track_to_merge['speed_history'].copy()
                        else:
                            best_track['speed_history'].extend(track_to_merge['speed_history'])
                            # Keep only recent history
                            if len(best_track['speed_history']) > 10:
                                best_track['speed_history'] = best_track['speed_history'][-10:]
                    
                    # Remove the merged track
                    del self.player_tracks[track_id]
                    print(f"Merged track {track_id} into {best_track_id}")
            
            print(f"After merging tracks: {len(self.player_tracks)} total tracks")

    def merge_tracks_for_positions(self, positions):
        """Merge tracks that correspond to the same player based on position proximity"""
        if not self.player_tracks or len(positions) < 2:
            return
        
        # Find tracks that are close to these positions
        tracks_to_merge = []
        
        for track_id, track in self.player_tracks.items():
            if track['positions']:
                last_pos = track['positions'][-1]
                
                # Check if this track is close to any of the positions
                for pos in positions:
                    dist = np.sqrt((last_pos[0] - pos[0])**2 + (last_pos[1] - pos[1])**2)
                    if dist < 40:  # Threshold for considering tracks as the same player
                        tracks_to_merge.append(track_id)
                        break
        
        # If we found multiple tracks for the same player, merge them
        if len(tracks_to_merge) > 1:
            print(f"Merging {len(tracks_to_merge)} tracks for same player positions: {tracks_to_merge}")
            
            # Keep the track with the most history
            best_track_id = None
            max_history = 0
            
            for track_id in tracks_to_merge:
                track = self.player_tracks[track_id]
                if len(track['positions']) > max_history:
                    max_history = len(track['positions'])
                    best_track_id = track_id
            
            # Merge all other tracks into the best one
            for track_id in tracks_to_merge:
                if track_id != best_track_id:
                    track_to_merge = self.player_tracks[track_id]
                    best_track = self.player_tracks[best_track_id]
                    
                    # Merge position histories
                    if track_to_merge['positions']:
                        best_track['positions'].extend(track_to_merge['positions'])
                        
                        # Keep only the most recent positions
                        if len(best_track['positions']) > self.track_history_length:
                            best_track['positions'] = best_track['positions'][-self.track_history_length:]
                    
                    # Merge velocity data if available
                    if 'velocity' in track_to_merge and track_to_merge['velocity'] != (0, 0):
                        if 'velocity' not in best_track or best_track['velocity'] == (0, 0):
                            best_track['velocity'] = track_to_merge['velocity']
                        else:
                            # Average the velocities
                            v1 = best_track['velocity']
                            v2 = track_to_merge['velocity']
                            best_track['velocity'] = ((v1[0] + v2[0])/2, (v1[1] + v2[1])/2)
                    
                    # Merge speed data
                    if 'speed' in track_to_merge:
                        if 'speed' not in best_track:
                            best_track['speed'] = track_to_merge['speed']
                        else:
                            best_track['speed'] = (best_track['speed'] + track_to_merge['speed']) / 2
                    
                    # Merge speed history
                    if 'speed_history' in track_to_merge:
                        if 'speed_history' not in best_track:
                            best_track['speed_history'] = track_to_merge['speed_history'].copy()
                        else:
                            best_track['speed_history'].extend(track_to_merge['speed_history'])
                            # Keep only recent history
                            if len(best_track['speed_history']) > 10:
                                best_track['speed_history'] = best_track['speed_history'][-10:]
                    
                    # Remove the merged track
                    del self.player_tracks[track_id]
                    print(f"Merged track {track_id} into {best_track_id}")
            
            print(f"After merging tracks for positions: {len(self.player_tracks)} total tracks")

    def smooth_positions_temporally(self, current_positions, current_frame):
        """Apply temporal smoothing to player positions across frames"""
        if not self.player_tracks:
            return current_positions
        
        smoothed_positions = []
        
        for pos in current_positions:
            x, y = pos
            pos_tuple = (int(float(x)), int(float(y)))
            
            # Find the closest existing track
            closest_track_id = None
            min_dist = float('inf')
            
            for track_id, track in self.player_tracks.items():
                if track['positions']:
                    last_pos = track['positions'][-1]
                    dist = np.sqrt((last_pos[0] - pos_tuple[0])**2 + (last_pos[1] - pos_tuple[1])**2)
                    if dist < self.max_tracking_distance and dist < min_dist:
                        min_dist = dist
                        closest_track_id = track_id
            
            if closest_track_id is not None and min_dist < 15:  # Only smooth if very close match
                # Apply temporal smoothing
                track = self.player_tracks[closest_track_id]
                last_pos = track['positions'][-1]
                
                # Use much more conservative smoothing
                smoothing_factor = min(0.2, self.position_smoothing_factor)  # Cap at 0.2
                smoothed_x = int(last_pos[0] * (1 - smoothing_factor) + 
                               pos_tuple[0] * smoothing_factor)
                smoothed_y = int(last_pos[1] * (1 - smoothing_factor) + 
                               pos_tuple[1] * smoothing_factor)
                
                smoothed_positions.append((smoothed_x, smoothed_y))
                print(f"Smoothed position: {pos_tuple} -> ({smoothed_x}, {smoothed_y})")
            else:
                # No matching track or too far, use original position
                smoothed_positions.append(pos_tuple)
        
        return smoothed_positions

    def interpolate_positions_between_frames(self, current_positions, current_frame):
        """Interpolate positions for frames between detections"""
        if not self.player_tracks:
            return current_positions
        
        # Calculate frames since last processing
        frames_since_last = current_frame - self.last_processed_frame
        
        if frames_since_last <= 1:
            # No interpolation needed
            return current_positions
        
        # For each track, interpolate positions for intermediate frames
        for track_id, track in self.player_tracks.items():
            if track['positions'] and len(track['positions']) >= 2:
                # Get last two positions for interpolation
                pos1 = track['positions'][-2]  # Previous position
                pos2 = track['positions'][-1]  # Current position
                
                # Only interpolate if positions are reasonably close
                dist = np.sqrt((pos2[0] - pos1[0])**2 + (pos2[1] - pos1[1])**2)
                if dist > 50:  # Skip interpolation if positions are too far apart
                    continue
                
                # Calculate velocity for interpolation
                vx = (pos2[0] - pos1[0]) / frames_since_last
                vy = (pos2[1] - pos1[1]) / frames_since_last
                
                # Generate interpolated positions for intermediate frames (reduced)
                interpolated_positions = []
                for frame_offset in range(1, min(frames_since_last, 2)):  # Max 2 interpolated frames
                    interp_x = int(pos1[0] + vx * frame_offset)
                    interp_y = int(pos1[1] + vy * frame_offset)
                    interpolated_positions.append((interp_x, interp_y))
                
                # Store interpolated positions for this track
                self.interpolated_positions[track_id] = interpolated_positions
        
        return current_positions

    def apply_velocity_smoothing(self):
        """Apply temporal smoothing to velocity calculations"""
        for track_id, track in self.player_tracks.items():
            if len(track['positions']) >= 2:
                # Calculate current velocity
                current_pos = track['positions'][-1]
                prev_pos = track['positions'][-2]
                
                current_vx = current_pos[0] - prev_pos[0]
                current_vy = current_pos[1] - prev_pos[1]
                
                # Only smooth if velocity is reasonable (not too large)
                velocity_magnitude = np.sqrt(current_vx**2 + current_vy**2)
                if velocity_magnitude > 30:  # Skip smoothing for very large movements
                    track['velocity'] = (current_vx, current_vy)
                    continue
                
                # Smooth with previous velocity if available
                if 'velocity' in track and track['velocity'] != (0, 0):
                    prev_vx, prev_vy = track['velocity']
                    
                    # Use more conservative smoothing
                    smoothing_factor = min(0.3, self.velocity_smoothing_factor)  # Cap at 0.3
                    smoothed_vx = prev_vx * (1 - smoothing_factor) + current_vx * smoothing_factor
                    smoothed_vy = prev_vy * (1 - smoothing_factor) + current_vy * smoothing_factor
                    
                    track['velocity'] = (smoothed_vx, smoothed_vy)
                else:
                    track['velocity'] = (current_vx, current_vy)

    def draw_ellipse(self, frame, bbox, color, track_id=None):
        """Draw an ellipse under a player with optional track ID"""
        y2 = int(bbox[3])
        x_center = int((bbox[0] + bbox[2]) / 2)
        width = int(bbox[2] - bbox[0])

        # Draw ellipse
        cv2.ellipse(
            frame,
            center=(x_center, y2),
            axes=(int(width), int(0.35*width)),
            angle=0.0,
            startAngle=-45,
            endAngle=235,
            color=color,
            thickness=2,
            lineType=cv2.LINE_4
        )

        # Draw track ID box
        if track_id is not None:
            rectangle_width = 40
            rectangle_height = 20
            x1_rect = x_center - rectangle_width//2
            x2_rect = x_center + rectangle_width//2
            y1_rect = (y2 - rectangle_height//2) + 15
            y2_rect = (y2 + rectangle_height//2) + 15

            cv2.rectangle(frame,
                        (int(x1_rect), int(y1_rect)),
                        (int(x2_rect), int(y2_rect)),
                        color,
                        cv2.FILLED)
            
            x1_text = x1_rect + 12
            if track_id > 99:
                x1_text -= 10
            
            cv2.putText(
                frame,
                f"{track_id}",
                (int(x1_text), int(y1_rect + 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )

        return frame

    def stop_video_processing(self):
        self.stop_processing = True
        print("Processing stopped by user.")

    def analyze_motion_magnitude(self, motion_matrix):
        if motion_matrix is None:
            return 0.0
                    
        # Extract components
        tx = motion_matrix[0, 2]  # x translation
        ty = motion_matrix[1, 2]  # y translation
        
        # Approximate scaling from matrix (this is a simplification)
        scale = (motion_matrix[0, 0] + motion_matrix[1, 1]) / 2.0
        scale_change = abs(1.0 - scale)
        
        # Combine translation and scale for overall motion magnitude
        motion_mag = np.sqrt(tx*tx + ty*ty) + scale_change * 100.0
        return motion_mag

    def start_reference_selection(self):
        """Start the process of selecting a 5-yard reference segment"""
        if self.homography_matrix is not None:
            self.reference_points = []
            self.reference_complete = False
            self.instruction_label.config(text="Select two points exactly 5 yards apart on the field view")
            self.reference_btn.config(state=tk.DISABLED)
            self.field_canvas.bind("<Button-1>", self.on_field_reference_click)

    def on_field_reference_click(self, event):
        """Handle clicks for reference segment selection on field view"""
        if len(self.reference_points) < 2:
            # Scale coordinates back to original image size
            x = int(event.x / 0.8)
            y = int(event.y / 0.8)
            self.reference_points.append((x, y))
            
            # Draw point on canvas (using display coordinates)
            display_x = int(x * 0.8)
            display_y = int(y * 0.8)
            self.field_canvas.create_oval(display_x-5, display_y-5, display_x+5, display_y+5, 
                                  fill="green", outline="white")
            
            # Draw line if we have two points
            if len(self.reference_points) == 2:
                x1, y1 = self.reference_points[0]
                x2, y2 = self.reference_points[1]
                
                # Draw line using display coordinates
                display_x1 = int(x1 * 0.8)
                display_y1 = int(y1 * 0.8)
                display_x2 = int(x2 * 0.8)
                display_y2 = int(y2 * 0.8)
                self.field_canvas.create_line(display_x1, display_y1, display_x2, display_y2, 
                                      fill="green", width=2)
                
                # Calculate distance in field coordinates (no need for homography transform)
                distance_pixels = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                
                # Calculate pixels per yard
                self.pixels_per_yard = distance_pixels / 5.0  # 5 yards
                
                print(f"Reference segment set: {distance_pixels:.1f} pixels = 5 yards")
                print(f"Pixels per yard: {self.pixels_per_yard:.1f}")
                
                self.reference_complete = True
                self.field_canvas.unbind("<Button-1>")
                self.instruction_label.config(text="5-yard reference segment set. You can now process video.")
                self.process_video_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    
    video_path = "Sample1.mp4"
    clarifai_pat = "PAT HERE"
    
    app = FootballHomographyApp(root, video_path, clarifai_pat)
    app.run() 