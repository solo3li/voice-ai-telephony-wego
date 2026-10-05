"""MinIO & S3 client helpers for call recordings management."""
import json
import logging
from typing import Optional
import boto3
from botocore.client import Config
from django.conf import settings

logger = logging.getLogger(__name__)


def get_s3_client():
    """Return configured boto3 S3 client for MinIO/S3."""
    endpoint = getattr(settings, 'MINIO_ENDPOINT', 'http://minio:9000')
    access_key = getattr(settings, 'MINIO_ACCESS_KEY', 'minioadmin')
    secret_key = getattr(settings, 'MINIO_SECRET_KEY', 'minioadmin123')
    
    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east-1',
        config=Config(s3={'addressing_style': 'path'}, signature_version='s3v4')
    )


def ensure_minio_bucket() -> bool:
    """
    Ensure the call-recordings bucket exists in MinIO with public read policy.
    Can be invoked safely on startup or before starting egress.
    """
    bucket_name = getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings')
    try:
        s3 = get_s3_client()
        existing = [b['Name'] for b in s3.list_buckets().get('Buckets', [])]
        if bucket_name not in existing:
            s3.create_bucket(Bucket=bucket_name)
            logger.info(f"Created MinIO bucket '{bucket_name}'.")

        # Set public-read policy so clients can download/stream recordings directly
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            }]
        }
        s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        logger.info(f"Verified MinIO bucket '{bucket_name}' policy.")
        return True
    except Exception as e:
        logger.warning(f"MinIO bucket check failed (storage may be initializing): {e}")
        return False
