import io
import boto3

from clarifai_grpc.grpc.api import resources_pb2
from clarifai.client import User, Inputs
from clarifai_grpc.grpc.api import service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--pb-file', type=str, help='Path to the input .pb file', required=True)
    parser.add_argument('--app_id', type=str, help='Clarifai app ID', required=True)
    parser.add_argument('--user_id', type=str, help='Clarifai user ID', required=True)
    parser.add_argument('--dataset_name', type=str, default='mot-test', help='Dataset name to use or create')
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

    session = boto3.Session(profile_name='pff-ls', region_name='us-east-2')
    client = session.client('s3')

    bytes = io.BytesIO()
    client.download_fileobj(
        Bucket='fb2b-label-studio-projects',
        Key=data.video.url.split('s3://fb2b-label-studio-projects/')[1],
        Fileobj=bytes
    )

    input = Inputs.get_input_from_bytes(
        data.video.url.split('/')[-1].replace('.mp4', ''),
        video_bytes=bytes.getvalue(),
    )
    input.data.metadata.update({
        'purpose': 'mot-test',
        'source': 'pff-labelstudio',
        'source_url': data.video.url,
    })
    input.dataset_ids.append(dataset.id)

    annotations = []
    for frame_idx, frame in enumerate(data.frames[:30]):
        for i, region in enumerate(frame.data.regions):
            annotation = resources_pb2.Annotation()
            annotation.input_id = input.id
            f = annotation.data.frames.add()
            f.frame_info.time = max(1, int(frame_idx / 30.0 * 1000))  # Assuming 30 FPS
            r = f.data.regions.add()
            r.CopyFrom(region)
            r.data.concepts[0].id = concepts.get(r.data.concepts[0].name)
            # annotation.id = f'{input.id}_frame_{frame.id}_region_{i}'
            annotations.append(annotation)

    a.inputs().upload_inputs([input])

    channel = ClarifaiChannel.get_json_channel()
    stub = service_pb2_grpc.V2Stub(channel)
    user_app_id = resources_pb2.UserAppIDSet(user_id=u.id, app_id=a.id)
    metadata = (('authorization', f'Key {u.pat}'),)

    for i in range(0, len(annotations), 100):
        batch = annotations[i:i + 100]
        response = stub.PostAnnotations(
            service_pb2.PostAnnotationsRequest(
                user_app_id=user_app_id,
                annotations=batch
            ),
            metadata=metadata
        )
        if response.status.code != status_code_pb2.SUCCESS:
            print(f"Error uploading annotations: {response.status.description}")
            break