import boto3
import time

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb_client = boto3.client('dynamodb')

# Environment variables or configuration
TABLE_NAME = "YourDynamoDBTableName"
S3_BUCKET = "YourS3BucketName"
EXPORT_PREFIX = "YourExportPrefix/"
FIXED_EXPORT_PATH = "YourFixedExportPath/"

def delete_all_objects_in_prefix(bucket, prefix):
    """Deletes all objects under a specific S3 prefix."""
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in page_iterator:
        if "Contents" in page:
            delete_us = [{'Key': obj['Key']} for obj in page['Contents']]
            delete_response = s3.delete_objects(Bucket=bucket, Delete={'Objects': delete_us})
            print(f"Deleted objects: {delete_response}")
        else:
            print("No objects to delete.")

def copy_data_to_fixed_path(source_bucket, source_prefix, destination_path):
    """Recursively copy all data from source prefix to a fixed destination path."""
    response = s3_client.list_objects_v2(Bucket=source_bucket, Prefix=source_prefix)
    if 'Contents' in response and response['Contents']:
        for obj in response['Contents']:
            source_key = obj['Key']
            relative_path = source_key[len(source_prefix):]
            destination_key = destination_path + relative_path
            try:
                s3_client.copy_object(Bucket=source_bucket, CopySource={'Bucket': source_bucket, 'Key': source_key}, Key=destination_key)
                print(f"Copied {source_key} to {destination_key}")
            except Exception as e:
                print(f"Failed to copy {source_key}: {str(e)}")
    else:
        print("No contents found at the source prefix.")

def lambda_handler(event, context):
    try:
        delete_all_objects_in_prefix(S3_BUCKET, EXPORT_PREFIX)
        delete_all_objects_in_prefix(S3_BUCKET, FIXED_EXPORT_PATH)

        # Start the DynamoDB table export
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(TABLE_NAME)
        export_response = dynamodb_client.export_table_to_point_in_time(
            TableArn=table.table_arn,
            S3Bucket=S3_BUCKET,
            S3Prefix=EXPORT_PREFIX,
            ExportFormat="DYNAMODB_JSON",
            S3SseAlgorithm="AES256"
        )
        export_arn = export_response['ExportDescription']['ExportArn']
        print(f"New export initiated: {export_arn}")

        export_identifier = export_arn.split('/')[-1]
        latest_folder = EXPORT_PREFIX + "AWSDynamoDB/" + export_identifier + "/"
        print(f"Latest folder path: {latest_folder}")
        time.sleep(450)

        copy_data_to_fixed_path(S3_BUCKET, latest_folder, FIXED_EXPORT_PATH)

        return {
            "statusCode": 200,
            "body": f"Export from {latest_folder} copied to {FIXED_EXPORT_PATH}, ready for QuickSight"
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }

