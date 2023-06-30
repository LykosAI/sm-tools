from __future__ import annotations

import os

import b2sdk.exception as b2_exception
import b2sdk.file_version
from b2sdk.progress import AbstractProgressListener
from b2sdk.v2 import B2Api, InMemoryAccountInfo


class Uploader:
    def __init__(self, api_id: str, api_key: str, bucket_name: str):
        """Initializes the uploader."""
        info = InMemoryAccountInfo()
        self.api = B2Api(info)
        try:
            self.api.authorize_account(
                "production", api_id, api_key
            )
        except b2_exception.B2Error as e:
            raise RuntimeError(f"Could not connect to B2: {e}")

        self.bucket = self.api.get_bucket_by_name(bucket_name)

    def find_file(self, b2_path: str) -> b2sdk.file_version.DownloadVersion | None:
        """Searches for a file with the given bucket path."""
        # Try to download
        try:
            search = self.bucket.get_file_info_by_name(b2_path)
        except b2_exception.FileNotPresent:
            return None
        return search

    def upload(
        self,
        file_path: str,
        b2_path: str,
        progress_listener: AbstractProgressListener | None = None,
    ):
        """Uploads a file to the B2 bucket."""
        file_name = os.path.basename(file_path)
        base_name, ext = os.path.splitext(file_name)

        # Upload the file
        try:
            self.bucket.upload_local_file(
                local_file=file_path,
                file_name=b2_path,
                progress_listener=progress_listener,
            )
        except b2_exception.B2Error as e:
            raise RuntimeError(f"Could not upload file: {e}")

    @staticmethod
    def delete_file(file_version: b2sdk.file_version.DownloadVersion):
        """Deletes a file from the B2 bucket."""
        try:
            return file_version.delete()
        except b2_exception.B2Error as e:
            raise RuntimeError(f"Failed to delete file: {e}")
