"""Encrypted file storage adapter supporting local encrypted vault and S3/MinIO."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.security import decrypt_bytes, encrypt_bytes


class FileStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _s3_client(self):
        kwargs = {
            "region_name": self.settings.S3_REGION,
            "aws_access_key_id": self.settings.S3_ACCESS_KEY_ID or None,
            "aws_secret_access_key": self.settings.S3_SECRET_ACCESS_KEY or None,
        }
        if self.settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = self.settings.S3_ENDPOINT_URL
        return boto3.client("s3", **kwargs)

    def save_encrypted(
        self, user_id: str, extension: str, raw_bytes: bytes
    ) -> tuple[str, str, Optional[bytes]]:
        """Encrypt raw bytes at rest and store them in the configured backend.

        Returns (storage_path, backend, inline_blob). `inline_blob` is the encrypted payload the
        caller must persist on the row when the backend is "db"; otherwise it is None.
        """
        encrypted = encrypt_bytes(raw_bytes)
        file_key = f"{user_id}/{uuid.uuid4().hex}{extension}.enc"

        if self.settings.STORAGE_BACKEND == "db":
            return f"db://{file_key}", "db", encrypted

        if self.settings.STORAGE_BACKEND == "s3":
            client = self._s3_client()
            client.put_object(
                Bucket=self.settings.S3_BUCKET,
                Key=file_key,
                Body=encrypted,
                ServerSideEncryption="AES256",
            )
            return file_key, "s3", None

        base_dir = self.settings.storage_dir_path
        full_path = base_dir / file_key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(encrypted)
        return str(full_path), "local", None

    def load_decrypted(
        self, storage_path: str, backend: str = "local", inline_blob: Optional[bytes] = None
    ) -> bytes:
        if backend == "db":
            if not inline_blob:
                raise FileNotFoundError(f"Stored CV file not found: {storage_path}")
            return decrypt_bytes(inline_blob)

        if backend == "s3":
            client = self._s3_client()
            resp = client.get_object(Bucket=self.settings.S3_BUCKET, Key=storage_path)
            encrypted = resp["Body"].read()
            return decrypt_bytes(encrypted)

        p = Path(storage_path)
        if not p.exists():
            raise FileNotFoundError(f"Stored CV file not found: {storage_path}")
        return decrypt_bytes(p.read_bytes())

    def delete(self, storage_path: str, backend: str = "local") -> None:
        if backend == "db":
            return  # bytes live on the row and are removed with it
        if backend == "s3":
            try:
                client = self._s3_client()
                client.delete_object(Bucket=self.settings.S3_BUCKET, Key=storage_path)
            except ClientError:
                pass
            return

        p = Path(storage_path)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


storage_service = FileStorageService()
