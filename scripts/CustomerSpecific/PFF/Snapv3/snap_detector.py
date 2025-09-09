import cv2
import numpy as np
import os
import hashlib
import pickle
import time
from clarifai.client.model import Model
from sklearn.cluster import DBSCAN
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from moviepy import VideoFileClip, ImageSequenceClip
from itertools import groupby

# Set random seed for reproducibility
np.random.seed(42)

# Import SORT tracker - using ByteTracker as alternative
try:
    from sort import Sort
    TRACKER_AVAILABLE = True
except ImportError:
    # Fallback: implement simple centroid tracking
    TRACKER_AVAILABLE = False
    print("[DEBUG] SORT tracker not available, using simple centroid tracking")

class SimpleCentroidTracker:
    """Improved lightweight tracker with:
    - IoU-first matching (reduces ID churn when boxes jitter)
    - Center-distance secondary matching
    - Simple constant-velocity prediction for short occlusions
    - Exponential smoothing of box coordinates to reduce jitter
    - Graceful disappearance handling
    NOTE: This is intentionally minimal vs full SORT/ByteTrack but far less jittery than the old version.
    """
    def __init__(self,
                 max_disappeared: int = 12,
                 max_distance: float = 140.0,
                 iou_match_threshold: float = 0.3,
                 smoothing_alpha: float = 0.6,
                 velocity_damp: float = 0.7):
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.iou_match_threshold = iou_match_threshold
        self.alpha = np.clip(smoothing_alpha, 0.05, 0.95)
        self.velocity_damp = np.clip(velocity_damp, 0.0, 1.0)
        self.next_object_id = 0
        # Track state: id -> dict(bbox, centroid, velocity, disappeared, age, hits)
        self.tracks: dict[int, dict] = {}

    # ---------------- Internal helpers ----------------
    @staticmethod
    def _centroid(b):
        return np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], dtype=float)

    @staticmethod
    def _iou(a, b):
        xA = max(a[0], b[0]); yA = max(a[1], b[1])
        xB = min(a[2], b[2]); yB = min(a[3], b[3])
        inter = max(0, xB - xA) * max(0, yB - yA)
        if inter <= 0:
            return 0.0
        areaA = max(0, (a[2]-a[0])) * max(0, (a[3]-a[1]))
        areaB = max(0, (b[2]-b[0])) * max(0, (b[3]-b[1]))
        return inter / (areaA + areaB - inter + 1e-6)

    def _register(self, bbox):
        c = self._centroid(bbox)
        self.tracks[self.next_object_id] = {
            'bbox': np.array(bbox, dtype=float),
            'centroid': c.copy(),
            'velocity': np.zeros(2, dtype=float),
            'disappeared': 0,
            'age': 1,
            'hits': 1
        }
        self.next_object_id += 1

    def _deregister(self, tid):
        if tid in self.tracks:
            del self.tracks[tid]

    def _predict(self, track):
        # Simple constant velocity prediction; damp velocity to avoid runaway
        track['velocity'] *= self.velocity_damp
        track['centroid'] = track['centroid'] + track['velocity']
        # Shift bbox by same delta
        dx, dy = track['velocity']
        track['bbox'][0::2] += dx
        track['bbox'][1::2] += dy
        return track

    # ---------------- Public update ----------------
    def update(self, detections):
        # Normalize input (can be [] or np.array)
        if detections is None or len(detections) == 0:
            # Predict then mark disappearance
            remove = []
            for tid, tr in self.tracks.items():
                self._predict(tr)
                tr['disappeared'] += 1
                if tr['disappeared'] > self.max_disappeared:
                    remove.append(tid)
            for tid in remove:
                self._deregister(tid)
            return self._as_ndarray()

        dets = np.array(detections, dtype=float)
        boxes = dets[:, :4] if dets.ndim == 2 else dets[:4]

        # If no existing tracks -> register all
        if len(self.tracks) == 0:
            for b in boxes:
                self._register(b)
            return self._as_ndarray()

        # Step 1: predict existing tracks
        for tr in self.tracks.values():
            self._predict(tr)

        track_ids = list(self.tracks.keys())
        track_boxes = np.array([self.tracks[tid]['bbox'] for tid in track_ids])

        # IoU matrix
        iou_matrix = np.zeros((len(track_boxes), len(boxes)), dtype=float)
        for i, tb in enumerate(track_boxes):
            for j, db in enumerate(boxes):
                iou_matrix[i, j] = self._iou(tb, db)

        # Match by IoU greedily
        matched_tracks = set()
        matched_dets = set()
        # Flatten and sort by descending IoU
        flat = [(-iou_matrix[i, j], i, j) for i in range(iou_matrix.shape[0]) for j in range(iou_matrix.shape[1]) if iou_matrix[i, j] >= self.iou_match_threshold]
        flat.sort()
        for neg_iou, i, j in flat:
            if i in matched_tracks or j in matched_dets:
                continue
            matched_tracks.add(i); matched_dets.add(j)
            tid = track_ids[i]
            det_box = boxes[j]
            self._update_track(self.tracks[tid], det_box)

        # Remaining unmatched: distance based association
        remaining_tracks = [i for i in range(len(track_ids)) if i not in matched_tracks]
        remaining_dets = [j for j in range(len(boxes)) if j not in matched_dets]
        if remaining_tracks and remaining_dets:
            # Build distance matrix between predicted centers and detection centers
            rem_track_ids = [track_ids[i] for i in remaining_tracks]
            track_centers = np.array([self.tracks[tid]['centroid'] for tid in rem_track_ids])
            det_centers = np.array([self._centroid(boxes[j]) for j in remaining_dets])
            D = np.linalg.norm(track_centers[:, None, :] - det_centers[None, :, :], axis=2)
            # Greedy by distance
            pairs = []
            for ti in range(D.shape[0]):
                for dj in range(D.shape[1]):
                    if D[ti, dj] <= self.max_distance:
                        pairs.append((D[ti, dj], ti, dj))
            pairs.sort()
            used_t = set(); used_d = set()
            for dist, ti, dj in pairs:
                if ti in used_t or dj in used_d:
                    continue
                used_t.add(ti); used_d.add(dj)
                tid = rem_track_ids[ti]
                det_idx = remaining_dets[dj]
                self._update_track(self.tracks[tid], boxes[det_idx])
                matched_tracks.add(track_ids.index(tid))
                matched_dets.add(det_idx)

        # Unmatched detections -> register
        for j in range(len(boxes)):
            if j not in matched_dets:
                self._register(boxes[j])

        # Unmatched tracks -> mark disappeared
        for i, tid in enumerate(track_ids):
            if i not in matched_tracks:
                tr = self.tracks.get(tid)
                if tr:
                    tr['disappeared'] += 1
                    if tr['disappeared'] > self.max_disappeared:
                        self._deregister(tid)

        return self._as_ndarray()

    def _update_track(self, track, det_box):
        # Compute new centroid & velocity before smoothing
        new_centroid = self._centroid(det_box)
        # Velocity update (difference between (smoothed centroid) and new centroid)
        raw_vel = new_centroid - track['centroid']
        track['velocity'] = 0.5 * track['velocity'] + 0.5 * raw_vel  # blend to reduce spikes
        # Smooth bbox coordinates
        track['bbox'] = self.alpha * det_box + (1 - self.alpha) * track['bbox']
        track['centroid'] = self._centroid(track['bbox'])
        track['disappeared'] = 0
        track['age'] += 1
        track['hits'] += 1

    def _as_ndarray(self):
        out = []
        for tid, tr in self.tracks.items():
            b = tr['bbox']
            out.append([b[0], b[1], b[2], b[3], tid])
        return np.array(out) if out else np.array([])

class SnapDetector:
    def __init__(self, 
                 clarifai_model_url: str = "https://clarifai.com/pff-org/labelstudio-unified/models/unified-model", 
                 pat: str | None = None, 
                 debug_clarifai: bool = False, 
                 snap_search_fraction: float = 0.67, 
                 detection_cache_dir: str = "cache", 
                 enable_detection_cache: bool = True, 
                 min_active_los_players: int = 6, 
                 min_los_cluster_size: int = 8,
                 clarifai_allowed_labels: list[str] | None = None,
                 verbose: bool = False,
                 # NEW tuning knobs
                 los_smooth_window: int = 3,          # light causal smoothing for LOS velocities (was fixed at 5)
                 use_formation_blend: bool = True,     # allow disabling formation motion blend if over-smoothing
                 tracker_smooth_alpha: float = 0.75    # higher = follow detection more (less smoothing)
                 ):
        """SnapDetector orchestrates player detection, tracking, LOS estimation and snap timing.

        Key gating parameters:
        - min_active_los_players: minimum LOS players that must show movement to consider a snap.
        - min_los_cluster_size: minimum total players (both sides combined) that must form the LOS cluster.
        """
        # Store / validate basic params
        self.debug_clarifai = debug_clarifai
        self.verbose = verbose
        try:
            snap_search_fraction = float(snap_search_fraction)
        except Exception:
            snap_search_fraction = 0.67
        if not (0 < snap_search_fraction <= 1):
            snap_search_fraction = 0.67
        self.snap_search_fraction = snap_search_fraction
        self.enable_detection_cache = enable_detection_cache
        self.detection_cache_dir = detection_cache_dir

        # LOS / activation thresholds
        self.min_active_los_players = max(1, int(min_active_los_players))
        self.min_los_cluster_size = max(4, int(min_los_cluster_size))  # total players across both sides
        self._last_los_cluster_size = 0

        # Clarifai model setup
        self.pat = pat or os.getenv("CLARIFAI_PAT")
        if not self.pat:
            raise ValueError("Clarifai PAT not provided. Set CLARIFAI_PAT environment variable or pass pat parameter.")
        self.model = Model(url=clarifai_model_url, pat=self.pat)

        # Allowed detection labels (model may return non-player objects). Case-insensitive.
        if clarifai_allowed_labels is None:
            clarifai_allowed_labels = ['player','players']
        base_labels = {s.lower() for s in clarifai_allowed_labels}
        augmented = set(base_labels)
        for term in list(base_labels):
            if term.endswith('s') and len(term) > 3:
                augmented.add(term[:-1])
            elif not term.endswith('s') and len(term) > 2:
                augmented.add(term + 's')
        self.allowed_concepts_lower = augmented
        if self.debug_clarifai:
            print(f"[CLARIFAI DEBUG] Allowed labels set size={len(self.allowed_concepts_lower)} sample={list(self.allowed_concepts_lower)[:8]}")

        # Debug controls
        self.debug_los_ids = False
        self._debug_frames_logged = 0

        # Prepare cache dir
        if self.enable_detection_cache:
            os.makedirs(self.detection_cache_dir, exist_ok=True)

        # Motion analysis & smoothing controls
        self.feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
        self.lk_params = dict(winSize=(15, 15), maxLevel=2,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        self.los_smooth_window = max(1, int(los_smooth_window))
        self.use_formation_blend = bool(use_formation_blend)
        self.tracker_smooth_alpha = float(np.clip(tracker_smooth_alpha, 0.3, 0.95))

    # (Removed stray mis-indented attributes formerly outside __init__)

    # ---------------------- Caching Helpers ----------------------
    def _video_cache_key(self, video_path: str) -> str:
        try:
            stat = os.stat(video_path)
            base = f"{os.path.abspath(video_path)}|{int(stat.st_mtime)}|{stat.st_size}"
        except Exception:
            base = os.path.abspath(video_path)
        return hashlib.sha256(base.encode('utf-8')).hexdigest()[:24]

    def _cache_filepath(self, key: str) -> str:
        return os.path.join(self.detection_cache_dir, f"detections_{key}.pkl")

    def _load_cached_detections(self, video_path: str):
        if not self.enable_detection_cache:
            return None
        key = self._video_cache_key(video_path)
        fp = self._cache_filepath(key)
        if not os.path.isfile(fp):
            return None
        try:
            with open(fp, 'rb') as f:
                data = pickle.load(f)
            meta = data.get('meta', {})
            dets = data.get('detections')
            if not isinstance(dets, list):
                return None
            # Basic validation: frame count matches meta if present
            frame_count = meta.get('frame_count')
            if frame_count is not None and frame_count != len(dets):
                return None
            print(f"[CACHE] Loaded cached detections ({len(dets)} frames) for video: {os.path.basename(video_path)}")
            return dets
        except Exception as e:
            print(f"[CACHE] Failed to load cache ({e}), regenerating.")
            return None

    def _save_cached_detections(self, video_path: str, detections: list, fps: float, total_frames: int):
        if not self.enable_detection_cache:
            return
        key = self._video_cache_key(video_path)
        fp = self._cache_filepath(key)
        meta = {
            'video_path': os.path.abspath(video_path),
            'fps': fps,
            'frame_count': total_frames,
        }
        try:
            with open(fp, 'wb') as f:
                pickle.dump({'meta': meta, 'detections': detections}, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"[CACHE] Saved detections cache to {fp}")
        except Exception as e:
            print(f"[CACHE] Failed to save cache: {e}")

    def detect_field_points(self, frame: np.ndarray) -> np.ndarray:
        """Detect stable points on the field for camera motion tracking."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.goodFeaturesToTrack(gray, mask=None, **self.feature_params)
    
    def track_motion(self, prev_frame: np.ndarray, curr_frame: np.ndarray, prev_points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Track motion between frames using optical flow."""
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
        
        new_points, status, error = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, 
                                                            prev_points, None, 
                                                            **self.lk_params)
        return new_points, status

    def detect_players(self, frame: np.ndarray) -> List[Dict]:
        """Detect players using Clarifai model.

        Converts frame to JPEG bytes and calls model.predict_by_bytes.
        Expects detection model returning regions with region_info.bounding_box.
        Returns numpy array shaped (N,5): [x1,y1,x2,y2,confidence]
        If response does not include regions, returns empty array.
        """
        try:
            success, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not success:
                return np.empty((0, 5))
            image_bytes = buf.tobytes()
            prediction = self.model.predict_by_bytes(image_bytes)
            if self.debug_clarifai and self._debug_frames_logged < 5:
                print("[CLARIFAI DEBUG] Raw prediction object type:", type(prediction))
                try:
                    import pprint
                    pp = pprint.PrettyPrinter(depth=6)
                    print("[CLARIFAI DEBUG] Full raw prediction object:")
                    pp.pprint(prediction.__dict__ if hasattr(prediction, '__dict__') else prediction)
                except Exception as dbg_e:
                    print("[CLARIFAI DEBUG] error introspecting prediction:", dbg_e)
                self._debug_frames_logged += 1
            outputs = getattr(prediction, 'outputs', [])
            if not outputs:
                if self.debug_clarifai and self._debug_frames_logged <= 10:
                    print("[CLARIFAI DEBUG] No outputs attribute or empty outputs in prediction")
                return np.empty((0, 5))
            first_output = outputs[0]
            regions = []
            if hasattr(first_output, 'data') and first_output.data is not None:
                raw_regions = getattr(first_output.data, 'regions', [])
                try:
                    regions = list(raw_regions) if raw_regions else []
                except Exception:
                    regions = raw_regions if isinstance(raw_regions, list) else []
            if self.debug_clarifai and self._debug_frames_logged <= 10:
                print(f"[CLARIFAI DEBUG] Extracted regions count={len(regions)}")
            if not regions:
                if self.debug_clarifai and self._debug_frames_logged <= 10:
                    data_obj = getattr(first_output, 'data', None)
                    possible_concepts = getattr(data_obj, 'concepts', []) if data_obj else []
                    print(f"[CLARIFAI DEBUG] No regions returned this frame. concepts_len={len(possible_concepts)}")
                return np.empty((0, 5))
            h, w = frame.shape[:2]
            detections = []
            region_concepts_all = []  # store concepts for debug summary
            for r in regions:
                try:
                    bb = r.region_info.bounding_box
                    top = getattr(bb, 'top_row', 0.0)
                    left = getattr(bb, 'left_col', 0.0)
                    bottom = getattr(bb, 'bottom_row', 0.0)
                    right = getattr(bb, 'right_col', 0.0)
                    x1 = max(0, left * w)
                    y1 = max(0, top * h)
                    x2 = min(w, right * w)
                    y2 = min(h, bottom * h)
                    concepts = getattr(r.data, 'concepts', []) if hasattr(r, 'data') else []
                    concept_names = [getattr(c, 'name', '') for c in concepts] if concepts else []
                    region_concepts_all.append(concept_names)
                    if self.debug_clarifai and self._debug_frames_logged <= 15:
                        print(f"[CLARIFAI DEBUG] Region concepts: {concept_names}")
                    # Filter by allowed labels; skip if none match
                    if self.allowed_concepts_lower and concept_names:
                        if not any(name.lower() in self.allowed_concepts_lower for name in concept_names):
                            if self.debug_clarifai and self._debug_frames_logged <= 15:
                                print(f"[CLARIFAI DEBUG] -> filtered OUT (no allowed labels match)")
                            continue
                    # Confidence: prefer highest among allowed concepts; fallback to first
                    conf = 0.0
                    if concepts:
                        filtered = [c for c in concepts if getattr(c,'name','').lower() in self.allowed_concepts_lower] if self.allowed_concepts_lower else concepts
                        if filtered:
                            conf = max((getattr(c,'value',0.0) or 0.0) for c in filtered)
                        else:
                            conf = getattr(concepts[0], 'value', 0.0) or 0.0
                    detections.append([x1, y1, x2, y2, float(conf)])
                    if self.debug_clarifai and self._debug_frames_logged <= 15:
                        print(f"[CLARIFAI DEBUG] -> kept box {(int(x1),int(y1),int(x2),int(y2))} conf={conf:.3f}")
                except Exception as rex:
                    if self.debug_clarifai and self._debug_frames_logged <= 15:
                        print(f"[CLARIFAI DEBUG] Region parse error: {rex}")
                    continue
            if not detections:
                if self.debug_clarifai and self._debug_frames_logged <= 15:
                    print("[CLARIFAI DEBUG] All regions filtered or invalid. Region concept sets: ")
                    for idx, cn in enumerate(region_concepts_all):
                        print(f"   - Region {idx}: {cn}")
                return np.empty((0, 5))
            det_array = np.array(detections, dtype=float)
            if self.debug_clarifai and self._debug_frames_logged <= 15:
                mean_w = np.mean(det_array[:,2]-det_array[:,0]) if len(det_array) else 0
                mean_h = np.mean(det_array[:,3]-det_array[:,1]) if len(det_array) else 0
                print(f"[CLARIFAI DEBUG] Parsed {len(det_array)} detections kept after filtering. Mean box size: {mean_w:.1f}x{mean_h:.1f}")
            return det_array
        except Exception:
            return np.empty((0, 5))
    
    def identify_main_formation_players(self, players: np.ndarray) -> tuple:
        """Identify LOS cluster (largest linear cluster) and apply weights.

        Steps:
          1. Extract player centers; quick exit if none.
          2. Optional subsample if detections extremely large (safety only).
          3. Multi-scale DBSCAN (tight -> loose) with early exit once cluster is plausible.
          4. Refine cluster with PCA-derived line (orientation-agnostic LOS).
          5. Enforce minimum LOS size; until reached return zero weights to suppress early false motion.
          6. Weight LOS players (slightly higher central weights) and zero others.
        Returns (players, weights_array)
        """
        start_time = time.time()
        n = len(players)
        if n == 0:
            return players, np.zeros(0)

        centers = np.column_stack(((players[:, 0] + players[:, 2]) / 2.0,
                                    (players[:, 1] + players[:, 3]) / 2.0))

        # Safety subsample for pathological detection counts
        if n > 150:
            idx_sample = np.linspace(0, n - 1, 150).astype(int)
            centers_sample = centers[idx_sample]
        else:
            idx_sample = None
            centers_sample = centers

        eps_values = [70, 85, 100, 120, 140]
        best_indices: list[int] = []
        best_len = 0
        for eps in eps_values:
            if n < 3:
                break
            try:
                target = centers_sample if idx_sample is not None else centers
                min_samples = max(3, min(6, target.shape[0] // 2))
                clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(target)
                labels = clustering.labels_
                for lbl in set(labels):
                    if lbl < 0:
                        continue
                    idxs = np.where(labels == lbl)[0].tolist()
                    if idx_sample is not None:
                        idxs = [int(idx_sample[i]) for i in idxs if i < len(idx_sample)]
                    if len(idxs) > best_len:
                        best_len = len(idxs)
                        best_indices = idxs
                if best_len >= 7:  # early success
                    break
            except Exception:
                continue

        if best_len == 0:
            self._last_los_cluster_size = 0
            if self.verbose:
                print(f"[DEBUG] LOS clustering: n={n} no cluster found (time={(time.time()-start_time)*1000:.1f} ms)")
            return players, np.zeros(n)

        refined = self.refine_to_horizontal_line(centers, best_indices)
        los_indices = refined if len(refined) >= 3 else best_indices
        self._last_los_cluster_size = len(los_indices)

        if len(los_indices) < self.min_los_cluster_size:
            # Not enough players yet for reliable LOS-driven snap detection
            duration = (time.time() - start_time) * 1000.0
            if self.verbose:
                print(f"[DEBUG] LOS clustering: n={n} provisional_size={len(los_indices)} < min({self.min_los_cluster_size}) took={duration:.1f} ms")
            return players, np.zeros(n)

        # Weight computation
        weights = np.zeros(n)
        line_centroid = centers[los_indices].mean(axis=0)
        dists = np.linalg.norm(centers[los_indices] - line_centroid, axis=1)
        if dists.size:
            max_d = dists.max() + 1e-6
            for idx, dist in zip(los_indices, dists):
                weights[idx] = 8.0 + 2.0 * (1 - dist / max_d)
        else:
            weights[los_indices] = 10.0

        duration = (time.time() - start_time) * 1000.0
        if self.verbose:
            print(f"[DEBUG] LOS clustering: n={n} los_size={len(los_indices)} best_len={best_len} took={duration:.1f} ms")
        return players, weights
    
    def find_densest_cluster(self, centers: np.ndarray) -> list:
        """Find the indices of players in the densest cluster"""
        if len(centers) < 3:
            return list(range(len(centers)))
        
        # Use tight clustering to find the main group
        tight_eps = 80  # Very tight clustering for LOS detection
        min_samples = max(3, min(5, len(centers) // 2))
        
        clustering = DBSCAN(eps=tight_eps, min_samples=min_samples).fit(centers)
        labels = clustering.labels_
        
        # Find the largest valid cluster
        valid_labels = labels[labels >= 0]
        if len(valid_labels) == 0:
            # No tight clusters, try looser clustering
            clustering = DBSCAN(eps=120, min_samples=3).fit(centers)
            labels = clustering.labels_
            valid_labels = labels[labels >= 0]
        
        if len(valid_labels) == 0:
            # Still no clusters, return all players
            return list(range(len(centers)))
        
        # Find the largest cluster
        unique_labels, counts = np.unique(valid_labels, return_counts=True)
        largest_cluster_label = unique_labels[np.argmax(counts)]
        
        # Return indices of players in the largest cluster
        cluster_indices = np.where(labels == largest_cluster_label)[0]
        return cluster_indices.tolist()
    
    def refine_to_horizontal_line(self, centers: np.ndarray, cluster_indices: list) -> list:
        """
        From a cluster of players, find those that form the tightest LINE (any orientation).
        Original implementation assumed a horizontal LOS (broadcast sideline high angle). However,
        many clips are shot from the sideline with the LOS appearing vertical or oblique in the image.
        We therefore:
          1. Fit a best‑fit line via PCA (first principal component) to the cluster.
          2. Compute perpendicular distances of each player to that line.
          3. Keep players within an adaptive perpendicular tolerance.
          4. (Optional) Validate the cluster is sufficiently linear (length >> width). If not, fall back.
        Returned indices correspond to the original centers array indices (subset of cluster_indices).
        """
        if len(cluster_indices) < 3:
            return cluster_indices
        
        cluster_centers = centers[cluster_indices]
        # Center the data for PCA
        mean_pt = np.mean(cluster_centers, axis=0)
        centered = cluster_centers - mean_pt
        try:
            # SVD for principal components
            U, S, Vt = np.linalg.svd(centered, full_matrices=False)
            direction = Vt[0]  # Principal axis (unit vector)
        except Exception:
            # Fallback: return original cluster if PCA fails
            return cluster_indices

        # Project points onto principal axis and compute perpendicular distances
        projections = centered @ direction  # scalar along the line
        recon = np.outer(projections, direction)            # projected points on the line
        perpendicular_vecs = centered - recon               # residuals
        perp_dists = np.linalg.norm(perpendicular_vecs, axis=1)

        # Adaptive tolerance: base on robust dispersion (MAD) or std
        mad = np.median(np.abs(perp_dists - np.median(perp_dists))) + 1e-6
        robust_spread = 1.4826 * mad  # Approx std if normal
        std_perp = np.std(perp_dists)
        base_tol = np.median(perp_dists) + max(25, 2.2 * min(robust_spread if robust_spread > 1e-3 else std_perp, 60))
        # Cap tolerance so we do not absorb a large blob
        tolerance = min(base_tol, 70)

        los_mask = perp_dists <= tolerance
        los_indices = [cluster_indices[i] for i, keep in enumerate(los_mask) if keep]

        # Linearity test: along-line extent vs perpendicular spread
        line_length = (np.max(projections) - np.min(projections)) + 1e-6
        perp_spread = 2 * np.std(perp_dists) + 1e-6
        linear_ratio = line_length / perp_spread if perp_spread > 0 else 0

        # If too few kept OR line not elongated enough, relax tolerance slightly once
        if (len(los_indices) < 3 or linear_ratio < 2.2) and len(cluster_centers) >= 3:
            expanded_tol = min(tolerance * 1.35 + 10, 90)
            los_mask = perp_dists <= expanded_tol
            los_indices = [cluster_indices[i] for i, keep in enumerate(los_mask) if keep]
            # Recompute linearity quickly
            if len(los_indices) >= 3:
                sel_proj = projections[los_mask]
                sel_perp = perp_dists[los_mask]
                line_length = (np.max(sel_proj) - np.min(sel_proj)) + 1e-6
                perp_spread = 2 * np.std(sel_perp) + 1e-6
                linear_ratio = line_length / perp_spread if perp_spread > 0 else 0

        # Final fallback: if still not a convincing line, return original cluster (we'll weight later logic differently)
        if len(los_indices) < 3:
            return cluster_indices

        return los_indices
    
    def identify_horizontal_formation(self, players: np.ndarray, centers: np.ndarray) -> tuple:
        """
        Fallback method to identify horizontal formations when clustering fails.
        Looks for players aligned horizontally which is typical for line of scrimmage.
        """
        if len(players) < 3:
            return players, np.ones(len(players))
        
        # Group players by horizontal bands (y-coordinate proximity)
        y_coords = centers[:, 1]
        sorted_indices = np.argsort(y_coords)
        
        # Find the largest group of players within a horizontal band
        best_group_indices = []
        best_group_score = 0
        
        band_height = 80  # Vertical tolerance for horizontal line
        
        for i in range(len(sorted_indices)):
            current_y = y_coords[sorted_indices[i]]
            group_indices = []
            
            # Find all players within band_height of current player
            for j in range(len(sorted_indices)):
                if abs(y_coords[sorted_indices[j]] - current_y) <= band_height:
                    group_indices.append(sorted_indices[j])
            
            if len(group_indices) >= 3:  # Need at least 3 for a line
                # Score this group based on size and horizontal spread
                group_centers = centers[group_indices]
                horizontal_spread = np.max(group_centers[:, 0]) - np.min(group_centers[:, 0])
                group_score = len(group_indices) * min(horizontal_spread / 200.0, 2.0)
                
                if group_score > best_group_score:
                    best_group_score = group_score
                    best_group_indices = group_indices
        
        # Create weights based on the best horizontal formation found
        weights = np.ones(len(players))
        if len(best_group_indices) >= 3:
            for i in best_group_indices:
                weights[i] = 3.5  # High weight for horizontal formation players
            for i in range(len(players)):
                if i not in best_group_indices:
                    weights[i] = 0.4  # Lower weight for other players
        
        return players, weights

    def weight_by_density(self, players: np.ndarray, centers: np.ndarray) -> tuple:
        """Final fallback: weight players by local density around them."""
        weights = np.ones(len(players))
        
        for i, center in enumerate(centers):
            # Count nearby players within radius
            distances = np.linalg.norm(centers - center, axis=1)
            nearby_count = np.sum(distances < 120)  # Players within 120 pixels
            
            # Weight by local density (more nearby players = higher weight)
            weights[i] = min(nearby_count / 2.0, 3.0)  # Cap at 3.0
        
        return players, weights

    def calculate_motion_metrics(self, players: List[Dict], prev_players: List[Dict]) -> float:
        """Calculate weighted motion metrics focusing on main formation players."""
        if len(prev_players) == 0:
            return 0.0
        
        # Get players and their weights based on formation position
        current_players, current_weights = self.identify_main_formation_players(players)
        prev_players_filtered, prev_weights = self.identify_main_formation_players(prev_players)
        
        if len(current_players) == 0 or len(prev_players_filtered) == 0:
            return 0.0
        
        total_weighted_motion = 0
        total_weight = 0
        
        # Calculate weighted motion for all players
        for i, curr_player in enumerate(current_players):
            curr_center = np.array([(curr_player[0] + curr_player[2]) / 2, 
                                  (curr_player[1] + curr_player[3]) / 2])
            min_dist = float('inf')
            
            # Find closest previous player
            for prev_player in prev_players_filtered:
                prev_center = np.array([(prev_player[0] + prev_player[2]) / 2,
                                      (prev_player[1] + prev_player[3]) / 2])
                dist = np.linalg.norm(curr_center - prev_center)
                min_dist = min(min_dist, dist)
            
            # Only count reasonable movements with weighting
            if min_dist != float('inf') and min_dist < 200:
                weight = current_weights[i]
                total_weighted_motion += min_dist * weight
                total_weight += weight
                
        return total_weighted_motion / max(total_weight, 1)

    def calculate_los_player_velocities(self, tracks: np.ndarray, prev_tracks: np.ndarray) -> list:
        """
        Calculate velocities for LOS (main formation) players using track IDs for consistent matching.
        This eliminates detection jitter by tracking consistent objects over time.
        """
        if len(prev_tracks) == 0 or len(tracks) == 0:
            return []
        
        # Build dictionaries for current and previous track positions
        current_track_dict = {}
        prev_track_dict = {}
        
        for track in tracks:
            if len(track) >= 5:  # Ensure we have track ID
                track_id = int(track[4])
                center_x = (track[0] + track[2]) / 2
                center_y = (track[1] + track[3]) / 2
                current_track_dict[track_id] = (center_x, center_y)
            elif len(track) >= 4:  # Fallback for tracks without ID
                center_x = (track[0] + track[2]) / 2
                center_y = (track[1] + track[3]) / 2
                # Use index as track_id as fallback
                track_id = hash((center_x, center_y)) % 1000
                current_track_dict[track_id] = (center_x, center_y)
        
        for track in prev_tracks:
            if len(track) >= 5:  # Ensure we have track ID
                track_id = int(track[4])
                center_x = (track[0] + track[2]) / 2
                center_y = (track[1] + track[3]) / 2
                prev_track_dict[track_id] = (center_x, center_y)
            elif len(track) >= 4:  # Fallback for tracks without ID
                center_x = (track[0] + track[2]) / 2
                center_y = (track[1] + track[3]) / 2
                # Use index as track_id as fallback
                track_id = hash((center_x, center_y)) % 1000
                prev_track_dict[track_id] = (center_x, center_y)
        
        # Calculate velocities for tracks that exist in both frames
        velocities = []
        los_track_ids = set()  # Track which tracks are LOS players
        
        # First, identify which tracks belong to LOS formation (be very strict)
        if len(tracks) > 0:
            try:
                if tracks.ndim == 2 and tracks.shape[1] >= 4:
                    bbox_array = tracks[:, :4]
                    _, weights = self.identify_main_formation_players(bbox_array)
                    # ONLY use tracks with strong LOS weight (>=8 after new scaling)
                    los_indices = np.where(weights >= 8.0)[0]
                    
                    #print(f"[DEBUG] Total tracks: {len(tracks)}, LOS tracks identified: {len(los_indices)}")
                    
                    verbose_ids = []
                    for i in los_indices:
                        if i < len(tracks) and len(tracks[i]) >= 5:
                            tid = int(tracks[i][4])
                            los_track_ids.add(tid)
                            if self.debug_los_ids:
                                verbose_ids.append(str(tid))
                        elif i < len(tracks):
                            # Fallback for tracks without proper IDs
                            center_x = (tracks[i][0] + tracks[i][2]) / 2
                            center_y = (tracks[i][1] + tracks[i][3]) / 2
                            track_id = hash((center_x, center_y)) % 1000
                            los_track_ids.add(track_id)
                            if self.debug_los_ids:
                                verbose_ids.append(f"F{track_id}")
                    if self.debug_los_ids and verbose_ids:
                        print(f"[DEBUG] LOS track IDs this frame: {', '.join(verbose_ids)}")
                    
                    # If we have very few LOS players, don't analyze this frame
                    if len(los_track_ids) < max(2, self.min_los_cluster_size // 3):
                        print(f"[DEBUG] Too few LOS tracks ({len(los_track_ids)}), skipping velocity analysis")
                        return []
                        
                else:
                    print(f"[DEBUG] Unexpected tracks format: {tracks.shape if hasattr(tracks, 'shape') else type(tracks)}")
                    return []
            except Exception as e:
                print(f"[DEBUG] Error in LOS identification: {e}")
                return []  # Don't use fallback - better to have no data than bad data
        
        # Calculate velocities only for LOS tracks
        for track_id in current_track_dict:
            if track_id in prev_track_dict and track_id in los_track_ids:
                curr_pos = current_track_dict[track_id]
                prev_pos = prev_track_dict[track_id]
                
                # Calculate velocity (distance moved per frame)
                velocity = np.sqrt((curr_pos[0] - prev_pos[0])**2 + (curr_pos[1] - prev_pos[1])**2)
                
                # Filter out unreasonable velocities (likely tracking errors)
                if velocity < 150:  # Max reasonable velocity per frame
                    velocities.append(velocity)
        
        return velocities

    def detect_snap(self, video_path: str, task_id: str, processing_status: dict) -> Tuple[list, list, list, list]:
        """Process video, build motion histories, and return detected snap frame(s).

        Also records per-frame tracking/LOS overlay metadata for later GIF annotation.
        Returns: (snap_frames, motion_history, camera_motion_history, los_velocities_history)
        """
        # Overlay containers (one entry per frame read)
        self._overlay_frames = []
        self._overlay_video_path = video_path

        motion_history: list[float] = []
        camera_motion_history: list[float] = []
        los_velocities_history: list[list[float]] = []
        formation_motion_history: list[float] = []

        # Tracker selection
        if TRACKER_AVAILABLE:
            tracker = Sort(); print("[DEBUG] Using SORT tracker")
        else:
            tracker = SimpleCentroidTracker(smoothing_alpha=self.tracker_smooth_alpha); print(f"[DEBUG] Using simple centroid tracker (alpha={self.tracker_smooth_alpha})")

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames == 0:
            return [], [], [], []

        # State variables
        prev_frame = None
        prev_players = []  # previous tracks (post-tracker)
        last_detections = None
        persistence_frames = 3
        empty_streak = 0
        min_box_area = 25 * 25
        iou_dupe_threshold = 0.85
        los_ready = False
        los_min_frames = 8
        detection_frames_count = 0
        prev_points = None
        frame_count = 0
        processing_status[task_id]['status'] = 'Analyzing video frames...'

        cached_detections = self._load_cached_detections(video_path)
        detection_accum = [] if cached_detections is None else None
        fps = cap.get(cv2.CAP_PROP_FPS) if cap else 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            progress = 10 + int((frame_count / max(1, total_frames)) * 70)
            if progress > processing_status[task_id].get('progress', 0):
                processing_status[task_id]['progress'] = progress

            # ---------- Detection acquisition (cache or live) ----------
            if cached_detections is not None and frame_count - 1 < len(cached_detections):
                players = cached_detections[frame_count - 1]
                players = np.empty((0, 5)) if players is None or len(players) == 0 else players
                if len(players) > 0:
                    detection_frames_count += 1
                    if not los_ready and detection_frames_count >= los_min_frames:
                        los_ready = True
            else:
                players = self.detect_players(frame)
                if cached_detections is None:
                    if players is None or len(players) == 0:
                        empty_streak += 1
                        if last_detections is not None and empty_streak <= persistence_frames:
                            players = last_detections.copy()
                            if self.debug_clarifai and empty_streak == 1:
                                print(f"[CLARIFAI DEBUG] Using persisted detections (gap frame {empty_streak})")
                        else:
                            players = np.empty((0, 5))
                    else:
                        empty_streak = 0
                        last_detections = players.copy()
                        detection_frames_count += 1
                        if not los_ready and detection_frames_count >= los_min_frames:
                            los_ready = True
                    detection_accum.append(players.copy() if players is not None else np.empty((0, 5)))
                else:
                    if not los_ready and frame_count >= los_min_frames:
                        los_ready = True

            # ---------- Filter + de-duplicate ----------
            if len(players) > 0:
                wh = (players[:, 2] - players[:, 0]) * (players[:, 3] - players[:, 1])
                players = players[wh >= min_box_area]
            if len(players) > 1:
                keep = []
                suppressed = set()
                for i in range(len(players)):
                    if i in suppressed: continue
                    box_i = players[i]; keep.append(i)
                    for j in range(i + 1, len(players)):
                        if j in suppressed: continue
                        box_j = players[j]
                        xA = max(box_i[0], box_j[0]); yA = max(box_i[1], box_j[1])
                        xB = min(box_i[2], box_j[2]); yB = min(box_i[3], box_j[3])
                        inter = max(0, xB - xA) * max(0, yB - yA)
                        area_i = (box_i[2]-box_i[0])*(box_i[3]-box_i[1])
                        area_j = (box_j[2]-box_j[0])*(box_j[3]-box_j[1])
                        union = area_i + area_j - inter + 1e-6
                        if inter / union >= iou_dupe_threshold:
                            suppressed.add(j)
                players = players[keep] if len(keep) < len(players) else players

            # ---------- Tracking ----------
            if len(players) > 0:
                if TRACKER_AVAILABLE:
                    dets = np.column_stack([players, np.ones(len(players)) * 0.9])  # add dummy conf
                    tracks = tracker.update(dets)
                else:
                    tracks = tracker.update(players)
                tracked_players = tracks if len(tracks) > 0 else np.array([])
            else:
                tracked_players = np.array([])

            # ---------- Camera motion estimation ----------
            if prev_frame is not None:
                if prev_points is None:
                    prev_points = self.detect_field_points(prev_frame)
                if prev_points is not None:
                    new_points, status = self.track_motion(prev_frame, frame, prev_points)
                    if len(new_points) > 0:
                        cam_motion = float(np.mean(np.linalg.norm(new_points - prev_points, axis=1)))
                        camera_motion_history.append(cam_motion)
                        prev_points = new_points
                    else:
                        camera_motion_history.append(0.0)
                        prev_points = self.detect_field_points(frame)

            # ---------- LOS velocities ----------
            los_velocities = self.calculate_los_player_velocities(tracked_players, prev_players) if los_ready else []

            # ---------- Overlay capture ----------
            try:
                if len(tracked_players) > 0:
                    bboxes = tracked_players[:, :4]
                    _, wts = self.identify_main_formation_players(bboxes)
                    los_flags = (wts >= 8.0) if len(wts) else np.array([])
                    track_ids = []
                    for tr in tracked_players:
                        if len(tr) >= 5:
                            track_ids.append(int(tr[4]))
                        else:
                            cx = (tr[0] + tr[2]) / 2; cy = (tr[1] + tr[3]) / 2
                            track_ids.append(int(hash((cx, cy)) % 1000))
                    self._overlay_frames.append({'boxes': bboxes.copy(), 'los_flags': los_flags.copy() if len(los_flags) else np.array([]), 'track_ids': track_ids})
                else:
                    self._overlay_frames.append({'boxes': np.empty((0, 4)), 'los_flags': np.array([]), 'track_ids': []})
            except Exception:
                self._overlay_frames.append({'boxes': np.empty((0, 4)), 'los_flags': np.array([]), 'track_ids': []})

            # ---------- Histories accumulation ----------
            if len(los_velocities) == 0 and (not los_ready or empty_streak > persistence_frames):
                los_velocities_history.append([])
                motion_history.append(0.0)
                formation_motion_history.append(0.0)
            else:
                los_velocities_history.append(los_velocities)
                player_motion = float(np.mean(los_velocities)) if los_velocities else 0.0
                try:
                    formation_motion = self.calculate_motion_metrics(players, prev_players) if len(prev_players) else 0.0
                except Exception:
                    formation_motion = 0.0
                motion_history.append(player_motion)
                formation_motion_history.append(formation_motion)

            prev_frame = frame.copy()
            prev_players = tracked_players

        cap.release()
        if cached_detections is None and detection_accum and len(detection_accum) == frame_count:
            self._save_cached_detections(video_path, detection_accum, fps, frame_count)

        snap_frames = self.analyze_snap_patterns(
            motion_history,
            los_velocities_history,
            camera_motion_history,
            total_frames,
            formation_motion_history,
        )
    # Adjust snap earlier by ~200ms to account for reaction time between ball movement and broad player motion
        # https://www.researchgate.net/publication/343999999_Positional_differences_in_anticipation_timing_reaction_time_and_dynamic_balance_of_American_football_players
        try:
            if snap_frames and fps and fps > 0:
                pre_offset_frames = max(1, int(round(0.2 * fps)))  # 200ms
                adjusted = []
                for f in snap_frames:
                    adj = max(0, f - pre_offset_frames)
                    adjusted.append(adj)
                if self.verbose and adjusted != snap_frames:
                    print(f"[DEBUG] Applying 200ms pre-offset ({pre_offset_frames} frames). Original: {snap_frames} Adjusted: {adjusted}")
                snap_frames = adjusted
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Snap pre-offset adjustment skipped due to error: {e}")
        return snap_frames, motion_history, camera_motion_history, los_velocities_history

    def analyze_motion_patterns(self, motion_history: List[float]) -> List[int]:
        """
        Analyze motion patterns to identify multiple snap moments.
        Returns a list of frame numbers where snaps were detected.
        """
        if not motion_history:
            return []
            
        motion_array = np.array(motion_history)
        
        # Normalize and smooth the motion data
        motion_smooth = np.convolve(motion_array, np.ones(5)/5, mode='valid')
        if len(motion_smooth) < 2:
            return []
        
        # Calculate velocity (rate of change of motion)
        velocity = np.diff(motion_smooth)
        
        # Parameters for detection - tuned for line-of-scrimmage focused analysis
        window_size = 15  # Window to identify quiet periods  
        future_window = 25  # Look ahead for explosive motion
        min_separation = 120  # Minimum frames between snaps (4 seconds at 30fps)
        
        # Calculate motion intensity thresholds - more selective for line players
        motion_threshold = np.mean(motion_smooth) * 0.4  # Threshold for detecting quiet period
        explosion_threshold = np.percentile(motion_smooth, 85)  # Threshold for post-snap motion
        
        potential_snaps = []
        
        # Look for patterns in the valid range of frames
        for i in range(window_size, len(motion_smooth) - future_window):
            # Check for relative quiet period
            current_window = motion_smooth[i-window_size:i]
            future_window_motion = motion_smooth[i:i+future_window]
            
            # Conditions for snap detection:
            # 1. Current moment is relatively quiet
            is_quiet = np.mean(current_window) < motion_threshold
            
            # 2. Immediate future has explosive motion
            future_motion_max = np.max(future_window_motion)
            has_explosion = future_motion_max > explosion_threshold
            
            # 3. The explosion is sustained (multiple players moving)
            # Require at least 5 consecutive frames above a stricter threshold
            def max_consecutive_above(arr, threshold):
                return max((sum(1 for _ in group) for value, group in groupby(arr > threshold) if value), default=0)
            consecutive_high = max_consecutive_above(future_window_motion, explosion_threshold * 0.8)
            has_sustained_motion = consecutive_high >= 5  # Require at least 5 consecutive frames of high motion
            
            # 4. The rate of motion increase is sharp
            motion_increase_rate = np.max(np.diff(future_window_motion[:10])) # Look at immediate acceleration
            
            if is_quiet and has_explosion and has_sustained_motion:
                # Score this candidate based on multiple factors
                quiet_score = 1 - (np.mean(current_window) / motion_threshold)
                explosion_score = future_motion_max / explosion_threshold
                duration_score = consecutive_high / future_window
                acceleration_score = motion_increase_rate / np.mean(np.abs(velocity)) if np.mean(np.abs(velocity)) > 0 else 0
                
                # Combine scores with weights
                total_score = (quiet_score * 0.3 + 
                             explosion_score * 0.3 + 
                             duration_score * 0.2 +
                             acceleration_score * 0.2)
                
                potential_snaps.append((i + 2, total_score))  # Adding offset for smoothing window
        
        # Filter overlapping detections by keeping only the best in each region
        if not potential_snaps:
            return []
        
        # Sort by score (highest first)
        potential_snaps.sort(key=lambda x: x[1], reverse=True)
        
        selected_snaps = []
        for frame, score in potential_snaps:
            # Check if this snap is far enough from already selected snaps
            too_close = False
            for selected_frame in selected_snaps:
                if abs(frame - selected_frame) < min_separation:
                    too_close = True
                    break
            
            if not too_close:
                selected_snaps.append(frame)
        
        # Sort by frame number for final output
        selected_snaps.sort()
        return selected_snaps

    def analyze_snap_patterns(self, motion_history: list, los_velocities_history: list, camera_motion_history: list, total_frames: int, formation_motion_history: list | None = None, active_counts_history: list | None = None) -> list:
        """Improved robust snap detection with scoring & safeguards against early false triggers.

        Strategy:
          1. Build smoothed LOS mean velocity series (primary signal) + optional formation motion blend.
          2. Rolling baseline (median) & MAD per frame (window up to 120 prior frames) with floor.
          3. For each candidate frame inside search window, enforce:
               - Sufficient LOS active velocity count.
               - Stable LOS cluster (streak).
               - Absolute motion & derivative thresholds (not just z-score).
               - Preceding calm window.
               - Sustained elevation window.
          4. Score candidates (derivative + sustained mean + active count) & choose best, not first.
          5. Fallback derivative search restricted by same eligibility constraints.
        Returns list of at most one frame index.
        """
        if not los_velocities_history:
            return []

        mean_vel = np.array([np.mean(v) if v else 0.0 for v in los_velocities_history], dtype=float)
        los_counts = np.array([len(v) for v in los_velocities_history], dtype=int)
        if mean_vel.size == 0:
            return []

        # Light causal smoothing (configurable window)
        w = max(1, int(self.los_smooth_window))
        if w > 1 and mean_vel.size >= w:
            # causal: each index i uses values [i-w+1 .. i]
            kernel = np.ones(w) / w
            smooth = np.convolve(mean_vel, kernel, mode='full')[:mean_vel.size]
        else:
            smooth = mean_vel.copy()

        n = smooth.size
        search_end = int(max(30, min(n, self.snap_search_fraction * n)))

        # Optional formation motion incorporation
        if self.use_formation_blend and formation_motion_history:
            fm_arr = np.array(formation_motion_history, dtype=float)
            if fm_arr.size == n:
                if w > 1 and fm_arr.size >= w:
                    fm_s = np.convolve(fm_arr, np.ones(w)/w, mode='full')[:fm_arr.size]
                else:
                    fm_s = fm_arr
                # scale fm to LOS magnitude for blending
                scale = (np.max(smooth[:search_end]) + 1e-6)
                max_fm = np.max(fm_s[:search_end]) + 1e-6
                fm_scaled = fm_s / max_fm * scale
                combined = 0.7 * smooth + 0.3 * fm_scaled
            else:
                combined = smooth
        else:
            combined = smooth

        deriv = np.diff(combined, prepend=combined[0])

        # Threshold bases
        mad_global = np.median(np.abs(combined - np.median(combined))) + 1e-6
        # Parameter constants (slightly relaxed from prior version after review)
        calm_window = 10                 # was 12
        sustain_window = 12              # was 14
        mad_floor_abs = 0.45             # was 0.5
        min_abs_motion = 1.8             # relaxed from 2.0
        min_deriv_abs = 0.7              # relaxed from 0.75
        min_high_frac = 0.4              # unchanged
        earliest_frame_allowed = 40      # earlier allowance (was 55)
        active_count_req = max(self.min_active_los_players, int(self.min_los_cluster_size * 0.45))

        # Determine LOS stability streak (approximate) by counts threshold near cluster size target
        stable_mask = los_counts >= active_count_req
        stable_streak = np.zeros(n, dtype=int)
        for i in range(n):
            if stable_mask[i]:
                stable_streak[i] = stable_streak[i-1] + 1 if i > 0 else 1
            else:
                stable_streak[i] = 0

        candidates = []  # (frame, score, details dict)
        # Diagnostics containers when verbose
        diag_reasons = {
            'unstable': 0,
            'active_low': 0,
            'insufficient_prior': 0,
            'pre_not_calm': 0,
            'abs_elev': 0,
            'derivative': 0,
            'sustain_mean': 0,
            'sustain_high_frac': 0
        }
        for i in range(max(calm_window, earliest_frame_allowed), min(search_end, n - sustain_window)):
            if not stable_mask[i] or stable_streak[i] < 5:
                diag_reasons['unstable'] += 1
                continue
            if los_counts[i] < active_count_req:
                diag_reasons['active_low'] += 1
                continue
            # Rolling baseline window (up to 120 frames prior)
            w_start = max(0, i - 120)
            prior = combined[w_start:i] if i > 0 else combined[:1]
            if prior.size < calm_window:
                diag_reasons['insufficient_prior'] += 1
                continue
            baseline_med = np.median(prior)
            mad_local = np.median(np.abs(prior - baseline_med))
            mad_scaled = 1.4826 * mad_local
            # Apply floor that adapts a bit to baseline scale
            mad_scaled = max(mad_scaled, mad_floor_abs, 0.12 * baseline_med + 0.05)

            # Pre calm check
            pre = combined[i-calm_window:i]
            if np.mean(pre) > baseline_med + 1.2 * mad_scaled:
                diag_reasons['pre_not_calm'] += 1
                continue

            # Absolute & relative elevation
            val = combined[i]
            elev_thresh = baseline_med + max(2.2 * mad_scaled, min_abs_motion)  # further lowered from 2.7*mad
            passed_abs = val >= elev_thresh

            # Derivative check
            dval = deriv[i]
            deriv_thresh = max(min_deriv_abs, 0.65 * mad_scaled)
            passed_deriv = dval >= deriv_thresh
            # Strong derivative override for early ramp (even if abs elevation not yet met)
            strong_deriv = dval >= max(1.3 * mad_scaled, deriv_thresh * 1.6)
            if not (passed_abs and passed_deriv) and not strong_deriv:
                if not passed_abs:
                    diag_reasons['abs_elev'] += 1
                else:
                    diag_reasons['derivative'] += 1
                continue

            # Sustain window
            post = combined[i:i+sustain_window]
            post_mean = np.mean(post)
            high_thresh = baseline_med + 2 * mad_scaled
            high_frames = np.sum(post >= high_thresh)
            sustain_thresh_mean = baseline_med + max(1.6 * mad_scaled, 0.55 * min_abs_motion)
            if post_mean < sustain_thresh_mean:
                # allow if it's a strong derivative ramp start; we'll backtrack onset earlier
                if not strong_deriv:
                    diag_reasons['sustain_mean'] += 1
                    continue
            if high_frames < sustain_window * min_high_frac:
                if not strong_deriv:
                    diag_reasons['sustain_high_frac'] += 1
                    continue

            # Score components
            # Normalize derivative & sustain by local scales
            deriv_norm = dval / (mad_scaled + 1e-6)
            sustain_norm = (post_mean - baseline_med) / (3 * mad_scaled + 1e-6)
            active_norm = min(1.0, los_counts[i] / (self.min_los_cluster_size + 1e-6))
            score = 0.45 * deriv_norm + 0.35 * sustain_norm + 0.2 * active_norm
            if strong_deriv and not passed_abs:
                # ramp-start bonus to encourage earliest plausible onset
                score *= 1.15
            candidates.append((i, score, {
                'val': val,
                'baseline': baseline_med,
                'mad': mad_scaled,
                'deriv': dval,
                'post_mean': post_mean,
                'los_count': int(los_counts[i])
            }))

        if candidates:
            # Pick highest score; optionally slight bias to earliest among near-ties.
            candidates.sort(key=lambda x: (-x[1], x[0]))
            best = candidates[0]
            frame_idx, score, meta = best
            if self.verbose:
                print(f"[DEBUG] Snap candidate chosen frame={frame_idx} score={score:.2f} val={meta['val']:.2f} base={meta['baseline']:.2f} mad={meta['mad']:.2f} deriv={meta['deriv']:.2f} los_count={meta['los_count']}")
            return [int(frame_idx)]
        else:
            if self.verbose:
                total_frames_eval = sum(diag_reasons.values()) or 1
                diag_sorted = sorted(diag_reasons.items(), key=lambda x: -x[1])
                top_diag = ', '.join([f"{k}:{v}" for k,v in diag_sorted if v > 0])
                print(f"[DEBUG] No primary candidates passed. Rejection counts (frame evaluations={total_frames_eval}): {top_diag}")

        # Fallback: derivative peak within search_end that also meets minimal eligibility
        eligible = []
        for i in range(earliest_frame_allowed, min(search_end, n)):
            if not stable_mask[i] or los_counts[i] < active_count_req:
                continue
            eligible.append(i)
        if eligible:
            best_i = max(eligible, key=lambda k: deriv[k])
            # Onset backtrack: walk backwards while value still elevated above baseline + small margin and derivative positive
            # Recompute local baseline for backtracking window
            w_start = max(0, best_i - 120)
            prior = combined[w_start:best_i] if best_i > 0 else combined[:1]
            baseline_med = np.median(prior) if prior.size > 0 else np.median(combined[:max(5,best_i)])
            mad_local = np.median(np.abs(prior - baseline_med)) if prior.size > 0 else mad_global
            mad_scaled = max(1.4826 * mad_local, mad_floor_abs, 0.12 * baseline_med + 0.05)
            onset_thresh = baseline_med + max(1.6 * mad_scaled, 0.5 * min_abs_motion)
            onset = best_i
            for j in range(best_i-1, earliest_frame_allowed-1, -1):
                if not stable_mask[j]:
                    break
                if combined[j] < onset_thresh or deriv[j] <= 0:
                    break
                onset = j
            if self.verbose:
                print(f"[DEBUG] Fallback derivative snap frame={best_i} deriv={deriv[best_i]:.2f} onset_adjusted={onset}")
            return [int(onset)]

        # Ultimate fallback: global max derivative after earliest_frame_allowed
        if deriv.size > earliest_frame_allowed:
            idx = int(np.argmax(deriv[earliest_frame_allowed:]) + earliest_frame_allowed)
            if self.verbose:
                print(f"[DEBUG] Ultimate fallback snap frame={idx}")
            return [idx]
        return []

    def fallback_snap_detection(self, motion_smooth: np.ndarray, los_mean_smooth: np.ndarray, los_density_smooth: np.ndarray, smooth_window: int, allowed_max_frame: int, active_counts_s: np.ndarray | None = None) -> list:
        """
        Fallback method to find snap when strict criteria aren't met.
        Enhanced: incorporates extended sustain & density so later true snap outweighs early brief spikes.
        """
        print(f"[DEBUG] Running enhanced fallback snap detection on {len(motion_smooth)} frames")
        window_size = 22
        sustained_frames = 8
        extended_window = 55
        best_frame = -1
        best_score = 0
        for i in range(window_size, len(motion_smooth) - window_size):
            candidate_frame_index = i + smooth_window // 2
            if candidate_frame_index > allowed_max_frame:
                break
            pre_motion = motion_smooth[i-window_size:i]
            pre_los = los_mean_smooth[i-window_size:i]
            post_motion = motion_smooth[i:i+window_size]
            post_los = los_mean_smooth[i:i+window_size]
            post_density = los_density_smooth[i:i+window_size]
            if active_counts_s is not None:
                post_active = active_counts_s[i:i+window_size]
                if np.mean(post_active[:sustained_frames]) < (self.min_active_los_players - 0.4):
                    continue
            # Sustained portions
            pre_avg = np.mean(pre_motion)
            pre_los_avg = np.mean(pre_los)
            post_los_sustained_avg = np.mean(post_los[:sustained_frames])
            los_contrast = (post_los_sustained_avg - pre_los_avg) / (pre_los_avg + 1e-6)
            motion_contrast = (np.mean(post_motion[:sustained_frames]) - np.mean(pre_motion)) / (np.mean(pre_motion)+1e-6)
            consistency = 1.0 / (1.0 + np.std(post_los[:sustained_frames]))
            # Extended sustain
            ext_end = min(i + extended_window, len(motion_smooth))
            ext_los = los_mean_smooth[i:ext_end]
            ext_density = los_density_smooth[i:ext_end]
            if len(ext_los) > sustained_frames:
                ext_mean = np.mean(ext_los)
                ext_density_frac = np.mean(ext_density > np.percentile(los_density_smooth, 60))
            else:
                ext_mean = 0
                ext_density_frac = 0
            slope = np.mean(np.diff(post_los[:sustained_frames])) if sustained_frames > 1 else 0
            # Score combines contrast + extended sustain + density + slope
            base_score = (los_contrast * 0.32 + motion_contrast * 0.12 + consistency * 0.08 + (ext_mean / (np.percentile(los_mean_smooth,80)+1e-6)) * 0.23 + ext_density_frac * 0.17 + max(0,slope) * 0.05)
            if active_counts_s is not None:
                mean_active = np.mean(post_active[:sustained_frames])
                base_score *= (0.8 + 0.2 * min(1.0, mean_active / max(1, self.min_active_los_players)))
            # Temporal weighting (slight preference later)
            rel_pos = candidate_frame_index / max(allowed_max_frame,1)
            base_score *= (0.6 + 0.4 * rel_pos)
            if base_score > best_score and base_score > 0.2:
                best_score = base_score
                best_frame = candidate_frame_index
        if best_frame < 0:
            print("[DEBUG] Fallback reverting to max diff method")
            motion_diff = np.diff(motion_smooth)
            last_allowed = allowed_max_frame - (smooth_window // 2) - 1
            if last_allowed > 1:
                best_idx = int(np.argmax(motion_diff[:last_allowed]))
            else:
                best_idx = int(np.argmax(motion_diff))
            best_frame = best_idx + smooth_window // 2 + 1
            best_score = motion_diff[np.argmax(motion_diff)]
        print(f"[DEBUG] Enhanced fallback selected frame {best_frame} with score {best_score:.3f}")
        return [best_frame]

    def plot_los_velocities(self, los_velocities_history: list, output_path: str):
        """Plot the per-frame mean and max LOS velocities for visual inspection."""
        import matplotlib.pyplot as plt
        means = np.array([np.mean(v) if v else np.nan for v in los_velocities_history], dtype=float)
        maxs = np.array([np.max(v) if v else np.nan for v in los_velocities_history], dtype=float)

        def interpolate_nans(a: np.ndarray):
            if a.size == 0:
                return a
            isnan = np.isnan(a)
            if not isnan.any():
                return a
            idx = np.arange(a.size)
            valid = ~isnan
            if valid.sum() == 0:
                return np.zeros_like(a)
            # Forward/back fill via interpolation
            a_interp = a.copy()
            a_interp[isnan] = np.interp(idx[isnan], idx[valid], a[valid])
            return a_interp

        def smooth_series(a: np.ndarray, window: int = 5):
            if a.size < 3:
                return a
            window = max(1, window)
            if window == 1:
                return a
            kernel = np.ones(window) / window
            s = np.convolve(a, kernel, mode='same')
            return s

        # Prepare smoothed versions while preserving peak magnitudes
        w = max(3, int(self.los_smooth_window))
        means_interp = interpolate_nans(means)
        maxs_interp = interpolate_nans(maxs)
        means_s = smooth_series(means_interp, window=w)
        maxs_s = smooth_series(maxs_interp, window=w)

        # Re-mask regions that were originally NaN so lines break instead of flat zero baselines
        means_s[np.isnan(means)] = np.nan
        maxs_s[np.isnan(maxs)] = np.nan

        plt.figure(figsize=(14, 6))
        plt.plot(means, label='Mean LOS (raw)', color='lightgray', linewidth=1, alpha=0.7)
        plt.plot(maxs, label='Max LOS (raw)', color='silver', linewidth=0.8, alpha=0.5)
        plt.plot(means_s, label=f'Mean LOS (smoothed w={w})', color='tab:blue')
        plt.plot(maxs_s, label=f'Max LOS (smoothed w={w})', color='tab:orange', alpha=0.9)
        plt.xlabel('Frame Number')
        plt.ylabel('Velocity (pixels/frame)')
        plt.title('LOS Player Velocities (raw vs smoothed, gaps preserved)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

    def create_snap_gifs(self, video_path: str, snap_frames: List[int], output_dir: str, base_name: str, window_size: int = 30):
        """Create GIFs around each snap moment with player box overlays.

        Bounding box colors:
          - Green: player classified as LOS cluster member.
          - Yellow: other tracked player.
        If overlay data missing or mismatched, GIFs are generated without boxes.
        """
        if not snap_frames:
            return []

        clip = VideoFileClip(video_path)
        created_gifs = []
        for i, snap_frame in enumerate(snap_frames):
            start_time = max(0, (snap_frame - window_size) / clip.fps)
            end_time = min(clip.duration, (snap_frame + window_size) / clip.fps)
            if len(snap_frames) == 1:
                output_path = f"{output_dir}/{base_name}_snap.gif"
            else:
                output_path = f"{output_dir}/{base_name}_snap_{i+1}.gif"
            snap_subclip = clip.subclipped(start_time, end_time)
            frames = []
            start_frame_idx = int(round(start_time * clip.fps))
            target_frame_idx = snap_frame
            relative_target_idx = target_frame_idx - start_frame_idx
            expected_count = max(1, int(round((end_time - start_time) * clip.fps)))
            if relative_target_idx < 0: relative_target_idx = 0
            if relative_target_idx >= expected_count: relative_target_idx = expected_count - 1
            for f_idx, frame in enumerate(snap_subclip.iter_frames(fps=clip.fps, dtype="uint8")):
                frame = np.ascontiguousarray(frame.copy())
                # Detection/LOS bounding boxes intentionally omitted per latest requirement.
                if f_idx == relative_target_idx:
                    h, w = frame.shape[:2]
                    text = "SNAP"; font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = max(0.6, min(1.2, w / 800)); thickness = 2
                    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
                    x = (w - tw) // 2; y = int(th + 10)
                    cv2.putText(frame, text, (x, y), font, font_scale, (255, 50, 50), thickness, cv2.LINE_AA)
                frames.append(frame)
            gif_clip = ImageSequenceClip(frames, fps=10)
            gif_clip.write_gif(output_path, fps=10)
            gif_clip.close()
            created_gifs.append(output_path)
        clip.close()
        return created_gifs

    def plot_motion_graph(self, output_path: str, motion_history: List[float], camera_motion_history: List[float], snap_frames: List[int]):
        """Create a graph showing player and camera motion with all detected snap moments."""
        plt.figure(figsize=(14, 6))

        # Convert to arrays early
        motion_arr = np.array(motion_history) if motion_history else np.array([])
        cam_arr = np.array(camera_motion_history) if camera_motion_history else np.array([])

        # Smoothing + scaling pipeline (do NOT alter underlying detection arrays)
        def smooth_series(arr):
            if arr.size < 5:
                return arr
            w = 5
            pad = w // 2
            padded = np.pad(arr, (pad, pad), mode='edge')
            med = np.empty_like(arr)
            for i in range(arr.size):
                med[i] = np.median(padded[i:i+w])
            try:
                from scipy.ndimage import gaussian_filter1d
                g = gaussian_filter1d(med, sigma=1.3, mode='nearest')
            except Exception:
                kernel = np.ones(5)/5
                g = np.convolve(med, kernel, mode='same')
            # Spike dampening based on robust diff
            diffs = np.diff(g, prepend=g[0])
            mad = np.median(np.abs(diffs - np.median(diffs))) + 1e-6
            thresh = 5.0 * mad
            capped = g.copy()
            for i in range(1, capped.size):
                delta = capped[i] - capped[i-1]
                if abs(delta) > thresh:
                    capped[i] = capped[i-1] + np.sign(delta) * thresh
            return capped

        motion_scaled = smooth_series(motion_arr) * 100.0 if motion_arr.size else motion_arr
        camera_motion_scaled = smooth_series(cam_arr) * 100.0 if cam_arr.size else cam_arr

        # Combine for robust stats
        combined = np.concatenate([motion_scaled, camera_motion_scaled]) if (motion_scaled.size and camera_motion_scaled.size) else (motion_scaled if motion_scaled.size else camera_motion_scaled)

        clip_note = ""
        if combined.size:
            # Detect obvious terminal spike artifact: sudden jump in last 3% of frames exceeding earlier 99th pct * factor
            n = combined.size
            tail_start = int(n * 0.97)
            early = combined[:max(10, int(n*0.5))]
            p99_early = np.percentile(early, 99) if early.size else np.max(combined)
            tail_max = np.max(combined[tail_start:]) if tail_start < n else p99_early
            # If tail spike > 6x earlier high, treat as artifact and hard-clip to 2.5x p99_early
            hard_clip = None
            if tail_max > p99_early * 6:
                hard_clip = p99_early * 2.5
            # General robust clip at p98 (unless lower than hard_clip)
            p98 = np.percentile(combined, 98)
            clip_threshold = p98
            if hard_clip is not None:
                clip_threshold = min(clip_threshold, hard_clip)
            # Only clip if real max is much larger
            real_max = np.max(combined)
            if real_max > clip_threshold * 1.05:  # allow small headroom
                motion_scaled = np.clip(motion_scaled, None, clip_threshold)
                camera_motion_scaled = np.clip(camera_motion_scaled, None, clip_threshold)
                clip_note = f" (clipped > {clip_threshold:.1f})"

        if motion_scaled.size:
            plt.plot(motion_scaled, label='Player Motion (x100)', color="#78ff66", zorder=1)
            # Plot snaps after plotting motion (need y-limits after plotting base curves)
        if camera_motion_scaled.size:
            plt.plot(camera_motion_scaled, label='Camera Motion (x100)', linestyle='-.', color='#1f77b4', zorder=2)

        # After plotting curves (so y-limits exist), draw snap markers
        if snap_frames and motion_scaled.size:
            ylim_top = plt.ylim()[1]
            for i, snap_frame in enumerate(snap_frames):
                if i == 0:
                    plt.axvline(x=snap_frame, color='r', linestyle='--', label='Snap Moment', zorder=3)
                else:
                    plt.axvline(x=snap_frame, color='r', linestyle='--', zorder=3)
                plt.text(snap_frame, ylim_top * 0.92, f'Snap {i+1}', rotation=90, va='top', ha='right', fontsize=9, color='r', zorder=4)

        plt.xlabel('Frame Number')
        plt.ylabel('Motion Magnitude (scaled)')
        base_title = 'Motion Analysis for Snap Detection' if len(snap_frames) == 1 else f'Motion Analysis - {len(snap_frames)} Snaps Detected'
        plt.title(base_title + clip_note)
        plt.legend(loc='upper left')
        plt.grid(True, alpha=0.35)
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        # Optionally also save raw (unclipped) variant for debugging if clipping happened
        if clip_note:
            raw_path = output_path.replace('.png', '_raw.png')
            plt.figure(figsize=(14, 6))
            if motion_arr.size:
                plt.plot(motion_arr * 100.0, label='Player Motion raw (x100)', color='#78ff66')
            if cam_arr.size:
                plt.plot(cam_arr * 100.0, label='Camera Motion raw (x100)', linestyle='-.', color='#1f77b4')
            if snap_frames and motion_arr.size:
                for i, snap_frame in enumerate(snap_frames):
                    if i == 0:
                        plt.axvline(x=snap_frame, color='r', linestyle='--', label='Snap Moment')
                    else:
                        plt.axvline(x=snap_frame, color='r', linestyle='--')
            plt.xlabel('Frame Number')
            plt.ylabel('Motion Magnitude (scaled)')
            plt.title('Raw Motion (no clipping)')
            plt.legend(loc='upper left')
            plt.grid(True, alpha=0.35)
            plt.tight_layout()
            plt.savefig(raw_path)
            plt.close()
            print(f"[INFO] Motion graph clipping applied; raw variant saved to {raw_path}")