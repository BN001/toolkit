# Copyright (c) 2025 Stephen G. Pope
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.



import os
import boto3
import logging
import mimetypes  # для определения типа файла
from urllib.parse import urlparse, quote

# START ---- Добавил я для определения signature_version
from botocore.client import Config
# END ---- Добавил я для определения signature_version

logger = logging.getLogger(__name__)

    # Change by BN001: support for output_dir parameter
def upload_to_s3(file_path, s3_url, access_key, secret_key, bucket_name, region, output_dir=None):
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )

    # START ---- Добавил я для определения signature_version

    client = session.client(
        's3',
        endpoint_url=s3_url,
        config=Config(signature_version='s3')   # 🔑 фикс
    )
 
    # client = session.client('s3', endpoint_url=s3_url) # - я закоментил
    
    # END ---- Добавил я для определения signature_version

    try:
        import os
        basename = os.path.basename(file_path)

        # формируем путь в бакете (output_s3_path)
        if output_dir:
            if not output_dir.endswith("/"):
                output_dir += "/"
            output_s3_path = output_dir + basename
        else:
            output_s3_path = basename
        
        # определяем content_type для правильной загрузки видео, аудио, картинки и тд.  
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        # загружаем
        with open(file_path, 'rb') as data:
            client.upload_fileobj(
                data,
                bucket_name,
                output_s3_path,
                # ExtraArgs={'ACL': 'public-read'}
                ExtraArgs={
                        'ACL': 'public-read',
                        'ContentType': content_type
                    }
            )

        encoded_key = quote(output_s3_path)
        file_url = f"{s3_url}/{bucket_name}/{encoded_key}"
        return file_url
    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}")
        raise


# START ---- Добавил я list_objects_v2 - для получения списка файлов из бакета с указанием signature_version='s3v4'
# ⚡️ Новый метод для листинга
def list_files(s3_url, access_key, secret_key, bucket_name, region, prefix=""):
    """
    Возвращает список всех файлов в бакете (можно ограничить prefix).
    """
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    client = session.client(
        's3',
        endpoint_url=s3_url,
        config=Config(signature_version='s3v4')   # ⚡️ ВАЖНО: для list_objects
    )
    try:
        response = client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        files = []
        if "Contents" in response:
            for obj in response["Contents"]:
                files.append(obj["Key"])
        return files
    except Exception as e:
        logger.error(f"Error listing files in S3: {e}")
        raise


# END ---- Добавил я list_objects_v2 - для получения списка файлов из бакета

# START ---- Добавил я delete_from_s3 - для удаления файлов из бакета с указанием signature_version='s3v4'
def delete_from_s3(s3_url, access_key, secret_key, bucket_name, region, file_key):
    import boto3
    from botocore.client import Config

    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )

    client = session.client(
        "s3",
        endpoint_url=s3_url,
        config=Config(signature_version="s3v4")
    )

    response = client.delete_object(Bucket=bucket_name, Key=file_key)
    return response


# END ---- Добавил я delete_from_s3 - для удаления файлов из бакета
