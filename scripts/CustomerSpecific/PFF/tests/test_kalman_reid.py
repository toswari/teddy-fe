import numpy as np
import unittest
from context import api
from clarifai_grpc.grpc.api.resources_pb2 import Frame

class TestKalmanREIDTracker(unittest.TestCase):
    def setUp(self):
        self.params = {
            "max_dead": 100,
            "max_emb_distance": 0.0,
            "var_tracker": "manorm",
            "initialization_confidence": 0.65,
            "min_confidence": 0.25,
            "association_confidence": [0.25],
            "min_visible_frames": 0,
            "covariance_error": 100,
            "observation_error": 10,
            "max_distance": [0.6],
            "max_disappeared": 8,
            "distance_metric": "ciou",
            "track_aiid": ["Player"],
            "track_id_prefix": "0",
            "use_detect_box": 0,
            "project_track": 0,
            "project_fix_box_size": 0,
            "detect_box_fall_back": 0
        }
        self.tracker = api.reid.KalmanREID(**self.params)

    def test_tracker_initialization(self):
        self.assertIsInstance(self.tracker, api.reid.KalmanREID)
        for key, value in self.params.items():
            self.assertEqual(getattr(self.tracker, key), value)

    def test_init_state(self):
        self.tracker.init_state()

        self.assertListEqual(self.tracker.all_tracks, [])
        self.assertEqual(self.tracker.track_indices, {})

        self.assertIsInstance(self.tracker.tracker, api.tracker.Tracker)
        self.assertEqual(self.tracker.num_frames_processed, 0)

    def test_works(self):
        self.tracker.init_state()
        for i in range(5):
            frame = Frame()
            frame.data.image.image_info.width = 1280
            frame.data.image.image_info.height = 720

            score = 0.66 if i == 0 else 0.4

            region = frame.data.regions.add()
            region.region_info.bounding_box.top_row = 0.1
            region.region_info.bounding_box.bottom_row = 0.2
            region.region_info.bounding_box.left_col = 0.1
            region.region_info.bounding_box.right_col = 0.2
            region.value = score
    
            c = region.data.concepts.add()
            c.name = 'Player'
            c.id = 'Player'
            c.value = score

            self.tracker(frame.data)
            self.assertEqual(self.tracker.tracker.tracks[0].track_id, 0)
            self.assertTrue(
                (np.abs(self.tracker.tracker.tracks[0].prediction - np.array([[0.15],[0.15],[0.1],[0.1]])) < 0.5e-6).all()
            )
            self.assertAlmostEqual(self.tracker.tracker.tracks[0].confidence, score)

if __name__ == '__main__':
    unittest.main()
