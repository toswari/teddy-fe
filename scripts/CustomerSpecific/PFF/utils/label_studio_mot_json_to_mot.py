import json
import os
import pandas as pd
from PIL import Image as PILImage

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
            __df['category_id'] = __df.category.map({'Player': 0, 'Referee': 1})
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

#        mot_df = mot_df[mot_df.category == target_class]

        mot_df['frame'] += 1
        mot_df['object_id'] = mot_df['object_id'].map({j: i for i,j in enumerate(mot_df['object_id'].unique())})
        mot_df['conf'] = 1

        out_dir = os.path.join(out_dir, sequence_id)
        out_path = os.path.join(out_dir, 'gt.txt')
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        mot_df[['frame','object_id','x_pixel','y_pixel','xx_pixel','yy_pixel','conf','category']].to_csv(out_path,header=False,index=False)

        with open(os.path.join(out_dir, 'seqinfo.ini'), 'w') as f:
            f.write('[Sequence]\n')
            f.write(f'name={sequence_id}\n')
            f.write('imDir=img1\n')
            f.write('frameRate=25\n')
            f.write(f'seqLength={mot_df["frame"].max()}\n')
            f.write(f'imWdith={image_size[1]}\n')
            f.write(f'imHeight={image_size[0]}\n')
            f.write(f'imExt=.jpg\n')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='script to convert Label Studio JSON output of single video MOT labels to ~MOT format')
    p.add_argument('json_path')
    p.add_argument('out_dir')
    p.add_argument('--image-size', nargs=2, default=[720, 1280], help='image size in (H,W) format')
#    p.add_argument('--target-class', default='Player')
    args = p.parse_args()

    main(args.json_path, args.out_dir, args.image_size)
