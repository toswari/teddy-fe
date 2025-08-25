"""script to freeze a val set"""

import argparse
import pandas as pd
from main import FrameQuadMapDataset

parser = argparse.ArgumentParser()
parser.add_argument('root_directory', type=str)
parser.add_argument('csv_path', type=str)
args = parser.parse_args()

ds = FrameQuadMapDataset(
    root_directory=args.root_directory,
    csv_path=args.csv_path,
)

df0 = pd.read_csv(args.csv_path)
df0 = df0.set_index(['game_id', 'play_id'])

df = pd.DataFrame(ds.samples, columns=['video_path', 'start_frame', 'end_frame', 'label', 'snap_frame'])

df['game_id'] = df['video_path'].apply(lambda x: int(x.split('_')[1]))
df['play_id'] = df['video_path'].apply(lambda x: int(x.split('_')[2]))
df = df.set_index(['game_id', 'play_id'])
df = df.join(df0, how='left', lsuffix='_pred', rsuffix='_true')
df = df.reset_index()
df.to_csv('frozen_val_set.csv', index=False)