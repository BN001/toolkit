from flask import Blueprint, request, jsonify
import boto3
from botocore.client import Config
import os

v1_s3_delete_bp = Blueprint("v1_s3_delete", __name__)

@v1_s3_delete_bp.route("/v1/s3/delete", methods=["POST"])
def s3_delete():
    try:
        data = request.get_json()
        file_key = data.get("file_key")
        if not file_key:
            return jsonify({"error": "file_key is required"}), 400

        endpoint_url = os.getenv("S3_ENDPOINT_URL")
        access_key = os.getenv("S3_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_KEY")
        bucket_name = os.getenv("S3_BUCKET_NAME")
        region = os.getenv("S3_REGION")

        s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            endpoint_url=endpoint_url,
            config=Config(signature_version="s3v4"),
        )

        response = s3.delete_object(Bucket=bucket_name, Key=file_key)

        return jsonify({
            "status": "success",
            "file_key": file_key,
            "response": str(response)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
