import os
import boto3
from botocore.exceptions import NoCredentialsError

# Set environment variables for AWS credentials
os.environ['AWS_ACCESS_KEY_ID'] = ''
os.environ['AWS_SECRET_ACCESS_KEY'] = ''
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

def upload_file_to_s3(file_name, bucket_name, object_name=None, expiration=600):
    """
    Upload a file to S3 and return a presigned URL valid for a specified duration.
    :param file_name: Name of the file to upload
    :param bucket_name: Name of the S3 bucket
    :param object_name: S3 object name. If not specified, file_name is used
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL or None if the upload fails
    """
    # Use file_name as object_name if not specified
    if object_name is None:
        object_name = file_name

    # Create an S3 client
    s3_client = boto3.client('s3')

    try:
        # Upload the file
        s3_client.upload_file(file_name, bucket_name, object_name)

        # Generate a presigned URL for the uploaded object
        presigned_url = s3_client.generate_presigned_url('get_object',
                                                         Params={'Bucket': bucket_name,
                                                                 'Key': object_name},
                                                         ExpiresIn=expiration)
        return presigned_url
    except FileNotFoundError:
        print(f"The file {file_name} was not found.")
        return None
    except NoCredentialsError:
        print("Credentials not available.")
        return None

if __name__ == "__main__":
    # Define file name and S3 bucket details
    file_name = 'your_file.zip'  # Replace with your zip file name
    bucket_name = 'movemodels'  # Replace with your S3 bucket name
    # Upload the file and get the presigned URL valid for 10 minutes
    url = upload_file_to_s3(file_name, bucket_name, expiration=600)
    if url:
        print(f"File uploaded successfully. Temporary URL: {url}")
    else:
        print("File upload failed.")
