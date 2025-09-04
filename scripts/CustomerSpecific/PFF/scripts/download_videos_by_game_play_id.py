import argparse
import io
import os

import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("csv_path")
parser.add_argument("--aws_profile", type=str, default="pff-video", help="AWS profile name to use for S3 access")
parser.add_argument("--aws_region", type=str, default="us-east-2", help="AWS region to use for S3 access")
parser.add_argument("--output_dir", type=str, default=os.getcwd(), help="Directory to save the output video and result file")
args = parser.parse_args()

os.makedirs(args.output_dir, exist_ok=True)

new_data = pd.read_csv(args.csv_path)

import boto3
session = boto3.Session(profile_name=args.aws_profile, region_name=args.aws_region)
client = session.client('s3')

inputs = []
for i, row in new_data.iterrows():
    game_id, play_id, team_id, time = row
    s3_path_fmt = "s3://fb2b-photon-production-video/football/{league}/{game_id}/{play_id}_{team_id}_{suffix}.mp4"
    
    found = False
    for suffix in ['SL', 'V2', 'SB1']:
        for league in ['1', '2', '5', '6', '7']:
            s3_path = s3_path_fmt.format(league=league, game_id=game_id, play_id=play_id, team_id=team_id, suffix=suffix)
            bucket = s3_path.split('/')[2]
            key = '/'.join(s3_path.split('/')[3:])
            try:
                response = client.get_object(Bucket=bucket, Key=key)
                found = True
            except client.exceptions.NoSuchKey:
                continue
            if found:
                break
        if found:
            break

    if not found:
        print(f"Skipping {game_id}_{play_id}_{team_id} - file not found in any league (row {i})")
        continue
    with open(os.path.join(args.output_dir, f"{league}_{game_id}_{play_id}_{team_id}_{suffix}.mp4"), 'wb') as f:
        client.download_fileobj(Bucket=bucket, Key=key, Fileobj=f)