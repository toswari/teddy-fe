import os
import requests

from label_studio_mot_json_to_pb import convert
from label_studio_sdk.client import LabelStudio


if __name__ == "__main__":
    import argparse
    from concurrent.futures import ThreadPoolExecutor

    parser = argparse.ArgumentParser(description="Convert Label Studio MOT JSON to Protocol Buffers")
    parser.add_argument("out_dir", type=str, help="Output directory for the converted Protocol Buffers files")
    parser.add_argument("--image-size", nargs=2, type=int, default=[720, 1280], help="Image size in (H, W) format")
    args = parser.parse_args()

    key = os.environ.get("LABEL_STUDIO_API_KEY")

    ls = LabelStudio(
        base_url="https://label-studio.pffstaging.com/",
        api_key=key,
    )

    s = requests.Session()
    s.headers.update({
        "Authorization": f"Token {key}",
    })

    mot_projects = list(ls.projects.list(title="MOT"))

    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir)

    def process_project(project, session, out_dir, image_size):
        try:
            x = session.get(f"https://label-studio.pffstaging.com/api/projects/{project.id}/export?exportType=JSON")
            x.raise_for_status()
            
            print(f"Exported {len(x.json())} sequences from project {project.id}")
            data = convert(x.json()[0], image_size)
            id = '_'.join(data.video.url.split("/")[-1:])
            id = os.path.splitext(id)[0]
            with open(os.path.join(out_dir, f"{id}_gt.pb"), 'wb') as f:
                f.write(data.SerializeToString())
        except Exception as e:
            print(f"Error processing project {project.id}: {e}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_project, project, s, args.out_dir, args.image_size) 
                   for project in mot_projects]
        
        for future in futures:
            future.result()