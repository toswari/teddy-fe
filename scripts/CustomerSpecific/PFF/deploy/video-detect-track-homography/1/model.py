from clarifai_pff.runners.video import VideoStreamModel

import os

# We need this class so the Runner can pick it up
# and control the base folder
class R(VideoStreamModel):
    def __init__(self, folder=os.path.dirname(os.path.dirname(__file__))):
        super().__init__(folder=folder)