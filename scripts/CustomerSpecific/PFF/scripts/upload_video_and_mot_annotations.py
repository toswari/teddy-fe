import io
import boto3

from clarifai_grpc.grpc.api import resources_pb2
from clarifai.client import User, Inputs
from clarifai_grpc.grpc.api import service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from tqdm import tqdm

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--pb-file', type=str, help='Path to the input .pb file', required=True)
    parser.add_argument('--app_id', type=str, help='Clarifai app ID', required=True)
    parser.add_argument('--user_id', type=str, help='Clarifai user ID', required=True)
    parser.add_argument('--dataset_name', type=str, default='mot-test', help='Dataset name to use or create')
    parser.add_argument('--batch_size', type=int, default=100, help='Batch size for uploading annotations')
    parser.add_argument('--max_workers', type=int, default=4, help='Maximum number of worker threads for uploading')
    parser.add_argument('--video', type=str, default=None, help='Path to the video file (if needed)')
    args = parser.parse_args()

    with open(args.pb_file, 'rb') as f:
        # Assuming the file is a video, we can use Video data type
        data = resources_pb2.Data.FromString(f.read())

    u = User(args.user_id)
    a = u.app(args.app_id)

    concepts = {c.name: c.id for c in a.list_concepts()} or {'players': 'players', 'referee': 'referee'}

    datasets = list(a.list_datasets())
    dataset_name = args.dataset_name
    if dataset_name not in [d.id for d in datasets]:
        print(f"Creating dataset '{dataset_name}'")
        a.create_dataset(dataset_name)
    else:
        print(f"Dataset '{dataset_name}' already exists")

    dataset = a.dataset(dataset_name)

    if args.video is None:
        session = boto3.Session(profile_name='pff-ls', region_name='us-east-2')
        client = session.client('s3')

        video_bytes = io.BytesIO()
        client.download_fileobj(
            Bucket='fb2b-label-studio-projects',
            Key=data.video.url.split('s3://fb2b-label-studio-projects/')[1],
            Fileobj=video_bytes
        )
    else:
        with open(args.video, 'rb') as f:
            video_bytes = io.BytesIO(f.read())

    input = Inputs.get_input_from_bytes(
        data.video.url.split('/')[-1].replace('.mp4', ''),
        video_bytes=video_bytes.getvalue(),
    )
    input.data.metadata.update({
        'purpose': 'mot-test',
        'source': 'pff-labelstudio',
        'source_url': data.video.url,
    })
    input.dataset_ids.append(dataset.id)

    from clarifai_grpc.grpc.api.status import status_pb2, status_code_pb2
    annotations = []
    tracks = {}
    for frame_idx, frame in enumerate(data.frames):
        for i, region in enumerate(frame.data.regions):
            if region.track_id not in tracks:
                track = resources_pb2.AnnotationTrack()
                track.input_id = input.id
                track.id = region.track_id
                track.start_frame_nr = frame_idx
                track.end_frame_nr = frame_idx
                track.sample_rate_frame = 1
                # track.sample_rate_ms = int(1/30.0 * 1000)  # Assuming 30 FPS
                # track.start_frame_ms = int(frame_idx / 30.0 * 1000)  # Assuming 30 FPS
                track.concept.CopyFrom(region.data.concepts[0])
                track.concept.id = concepts.get(track.concept.name)
                track.status.CopyFrom(status_pb2.Status(code=status_code_pb2.ANNOTATION_TRACK_PENDING))
                tracks[region.track_id] = track

            tracks[region.track_id].end_frame_nr = frame_idx
            # tracks[region.track_id].end_frame_ms = int(frame_idx / 30.0 * 1000)  # Assuming 30 FPS

            annotation = resources_pb2.Annotation()
            annotation.input_id = input.id
            f = annotation.data.frames.add()
            f.frame_info.time = int(frame_idx / 30.0 * 1000)  # Assuming 30 FPS
            f.frame_info.number = frame_idx
            r = f.data.regions.add()
            r.CopyFrom(region)
            r.data.concepts[0].id = concepts.get(r.data.concepts[0].name)
            # annotation.id = f'{input.id}_frame_{frame.id}_region_{i}'
            annotations.append(annotation)

    a.inputs().upload_inputs([input])

    import time
    time.sleep(5) # wait for input to be fully processed

    channel = ClarifaiChannel.get_json_channel()
    stub = service_pb2_grpc.V2Stub(channel)
    user_app_id = resources_pb2.UserAppIDSet(user_id=u.id, app_id=a.id)
    metadata = (('authorization', f'Key {u.pat}'),)
    response = stub.PostAnnotationTracks(
        service_pb2.PostAnnotationTracksRequest(
            user_app_id=user_app_id,
            annotation_tracks=list(tracks.values()),
            input_id=input.id
        ),
        metadata=metadata
    )
    if response.status.code != status_code_pb2.SUCCESS:
        print(f"Error uploading annotation tracks: {response.status.description}. {response.status.details}")


    def go(u, batch):
        channel = ClarifaiChannel.get_json_channel()
        stub = service_pb2_grpc.V2Stub(channel)
        user_app_id = resources_pb2.UserAppIDSet(user_id=u.id, app_id=a.id)
        metadata = (('authorization', f'Key {u.pat}'),)

        response = stub.PostAnnotations(
            service_pb2.PostAnnotationsRequest(
                user_app_id=user_app_id,
                annotations=batch
            ),
            metadata=metadata
        )
        if response.status.code != status_code_pb2.SUCCESS:
            raise Exception(f"Error uploading annotations (batch {i // args.batch_size}): {response.status.description}. {response.status.details}")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = []
        for i in tqdm(range(0, len(annotations), args.batch_size)):
            batch = annotations[i:i + args.batch_size]
            futures.append(executor.submit(go, u, batch))

        for future in tqdm(as_completed(futures), total=len(futures)):
            try:
                future.result()
            except Exception as e:
                tqdm.write(f"Error occurred: {e}")
