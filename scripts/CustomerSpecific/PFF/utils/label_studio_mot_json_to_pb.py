import json
import os
import pandas as pd
from PIL import Image as PILImage

from clarifai_grpc.grpc.api.resources_pb2 import Data

def main(json_path, out_dir, image_size):
    with open(json_path) as f:
        mot_data = json.load(f)

    for sequence in mot_data:
        sequence_id = os.path.splitext(os.path.basename(sequence['data']['video']))[0]

        mot_annos = sequence['annotations'][0]['result']

        _dfs = []
        for a in mot_annos:
            __df = pd.DataFrame.from_records(a['value']['sequence'])
            __df['category'] = a['value']['labels'][0]
            __df['category'] = __df.category.map({'Player': 'players', 'Referee': 'referee'})
            __df['category_id'] = __df.category.map({'players': 0, 'referee': 1})
            __df['score'] = 1
            __df['object_id'] = a['id']

            #__df['file_name'] = __df['frame'].apply(lambda x: f"../mot-1/frames/{x+1}.jpg")
            #__df[['image_width', 'image_height']] = __df['file_name'].apply(lambda f: PILImage.open(f).size).tolist()
            __df['image_width'] = image_size[1] #1280
            __df['image_height'] = image_size[0] #720

            __df = __df.rename(columns={'id': 'box_id'})
            __df[['x','y','width','height']] /= 100
            __df[['x_pixel', 'y_pixel', 'width_pixel', 'height_pixel']] = __df[['x', 'y', 'width', 'height']].to_numpy() * __df[['image_width', 'image_height', 'image_width', 'image_height']].to_numpy()
            __df[['xx_pixel', 'yy_pixel']] = __df[['x_pixel', 'y_pixel']].to_numpy() + __df[['width_pixel', 'height_pixel']].to_numpy()
            __df[['left_col', 'top_row']] = __df[['x', 'y']]
            __df[['right_col', 'bottom_row']] = (__df[['x', 'y']].to_numpy() + __df[['width', 'height']].to_numpy())
            _dfs.append(__df)

        mot_df = pd.concat(_dfs)

        mot_df['frame'] += 1
        mot_df['object_id'] = mot_df['object_id'].map({j: i for i,j in enumerate(mot_df['object_id'].unique())})
        mot_df['conf'] = 1

        data = Data()
        for frame, group in mot_df.groupby('frame'):
            f = data.frames.add()
            f.data.image.image_info.width = group['image_width'].iloc[0]
            f.data.image.image_info.height = group['image_height'].iloc[0]
            for _, row in group.iterrows():
                r = f.data.regions.add()
                r.track_id = str(row['object_id'])
                box = r.region_info.bounding_box
                box.left_col, box.top_row, box.right_col, box.bottom_row = row['x'], row['y'], row['x'] + row['width'], row['y'] + row['height']
                r.value = row['score']
                r.data.concepts.add(id=str(row['category_id']), name=row['category'], value=row['score'])

        with open(os.path.join(out_dir, f'{sequence_id}_gt.pb'), 'wb') as f:
            f.write(data.SerializeToString())


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='script to convert Label Studio JSON output of single video MOT labels to ~MOT format')
    p.add_argument('json_path')
    p.add_argument('out_dir')
    p.add_argument('--image-size', nargs=2, default=[720, 1280], help='image size in (H,W) format')
    args = p.parse_args()

    main(args.json_path, args.out_dir, args.image_size)
