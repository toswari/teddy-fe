import os
import boto3
import tarfile
import zipfile
from botocore.exceptions import NoCredentialsError, ClientError
from time import sleep
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from google.protobuf.struct_pb2 import Struct

def upload_file_to_s3(file_name, bucket_name, aws_access_key_id, aws_secret_access_key, aws_default_region, object_name=None, expiration=600):
    os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key_id
    os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key
    os.environ['AWS_DEFAULT_REGION'] = aws_default_region
    if object_name is None:
        object_name = file_name
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_name, bucket_name, object_name)
        # Generate a presigned URL with an expiration time
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration
        )
        return presigned_url
    except FileNotFoundError:
        print(f"The file {file_name} was not found.")
        return None
    except NoCredentialsError:
        print("Credentials not available.")
        return None
    except ClientError as e:
        print(f"Failed to upload file: {e}")
        return None

def create_clarifai_model(stub, metadata, user_id, app_id, model_id, model_type_id):
    userDataObject = resources_pb2.UserAppIDSet(user_id=user_id, app_id=app_id)
    post_models_response = stub.PostModels(
        service_pb2.PostModelsRequest(
            user_app_id=userDataObject,
            models=[
                resources_pb2.Model(
                    id=model_id,
                    model_type_id=model_type_id,
                    notes='random notes here'
                )
            ]
        ),
        metadata=metadata
    )
    if post_models_response.status.code != status_code_pb2.SUCCESS:
        print(post_models_response.status)
        raise Exception("Post models failed, status: " + post_models_response.status.description)

def create_model_version(stub, metadata, user_id, app_id, model_id, model_zip_url):
    userDataObject = resources_pb2.UserAppIDSet(user_id=user_id, app_id=app_id)
    # This example was built for a Inceptionv2 Visual Detection model exported directly from the platform
    input_fields_params = Struct()
    input_fields_params.update({"image": "images"})
    output_fields_params = Struct()
    output_fields_params.update({"regions[...].data.concepts[...].id": "predicted_det_labels"})
    output_fields_params.update({"regions[...].data.concepts[...].value": "predicted_det_scores"})
    output_fields_params.update({"regions[...].region_info.bounding_box": "predicted_det_bboxes"})
    pretrained_config = resources_pb2.PretrainedModelConfig(
        input_fields_map=input_fields_params,
        output_fields_map=output_fields_params,
        model_zip_url=model_zip_url,
    )
    post_model_versions_response = stub.PostModelVersions(
        service_pb2.PostModelVersionsRequest(
            user_app_id=userDataObject,
            model_id=model_id,
            model_versions=[
                resources_pb2.ModelVersion(pretrained_model_config=pretrained_config)
            ],
        ),
        metadata=metadata,
    )
    if post_model_versions_response.status.code != status_code_pb2.SUCCESS:
        print(post_model_versions_response.status)
        raise Exception("Post model versions failed, status: " + post_model_versions_response.status.description)

def convert_tar_to_zip(tar_file_path, zip_file_path):
    temp_dir = 'temp_extracted_files'
    # Extract the .tar file
    with tarfile.open(tar_file_path, 'r') as tar:
        tar.extractall(temp_dir)
    # Create the .zip file
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    # Clean up the temporary directory [Need to fix this part *locks]
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            try:
                os.remove(os.path.join(root, file))
            except Exception as e:
                print(f"Error: {e}")
        try:
            os.rmdir(root)
        except Exception as e:
            print(f"Error: {e}")

def main(tar_file_path, zip_file_path, bucket_name, aws_access_key_id, aws_secret_access_key, aws_default_region, user_id, pat, app_id, model_id, model_type_id):
    # Convert TAR to ZIP
    convert_tar_to_zip(tar_file_path, zip_file_path)
    # Wait for the system to release the file
    sleep(5)
    # Upload to S3 [I'm using my personal bucket for testing due to access restrictions]
    url = upload_file_to_s3(zip_file_path, bucket_name, aws_access_key_id, aws_secret_access_key, aws_default_region)
    if url:
        print(f"File uploaded successfully. Temporary URL: {url}")
    else:
        print("File upload failed.")
        return

    # Clarifai model creation and versioning
    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)
    metadata = (('authorization', 'Key ' + pat),)
    try:
        create_clarifai_model(stub, metadata, user_id, app_id, model_id, model_type_id)
        sleep(5)
        create_model_version(stub, metadata, user_id, app_id, model_id, model_zip_url=url)
        print("Model and model version created successfully in Clarifai.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # While this script is functional, it is not perfect. Test before using on customer data.
    # User-defined variables
    tar_file_path = 'your_model.tar'  # Replace with your TAR file name
    zip_file_path = 'your_model.zip'  # Replace with your desired ZIP file name
    bucket_name = 'your_bucket_name'  # Replace with your S3 bucket name
    aws_access_key_id = 'your_aws_access_key_id'
    aws_secret_access_key = 'your_aws_secret_access_key'
    aws_default_region = 'us-east-2'

    user_id = 'your_user_id'
    pat = 'your_personal_access_token'
    app_id = 'your_app_id'
    model_id = 'your_model_id'
    model_type_id = 'your_model_type_id'

    main(tar_file_path, zip_file_path, bucket_name, aws_access_key_id, aws_secret_access_key, aws_default_region, user_id, pat, app_id, model_id, model_type_id)
