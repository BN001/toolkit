from flask import Blueprint, request, jsonify
import boto3
from botocore.client import Config
import os

v1_s3_delete_bp = Blueprint("v1_s3_delete", __name__)

@v1_s3_delete_bp.route("/v1/s3/delete", methods=["POST"])
def s3_delete():
    try:
        data = request.get_json()

        # поддерживаем и "file_key", и "file_keys"
        file_keys = []
        if "file_key" in data:
            file_keys = [data["file_key"]]
        elif "file_keys" in data:
            file_keys = data["file_keys"]

        if not file_keys:
            return jsonify({"error": "file_key or file_keys is required"}), 400

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

        objects = [{"Key": key} for key in file_keys]

        response = s3.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": objects}
        )

        return jsonify({
            "status": "success",
            "deleted": response.get("Deleted", []),
            "errors": response.get("Errors", [])
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
