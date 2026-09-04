"""Almacenamiento detrás de una interfaz: local en desarrollo, S3 en la nube.

Escribir esto el día 2 evita reescribir medio proyecto el día 6.
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import settings


class Storage(ABC):
    @abstractmethod
    def save(self, local_path: str, key: str) -> str: ...

    @abstractmethod
    def fetch(self, key: str, local_path: str) -> str: ...

    @abstractmethod
    def url(self, key: str) -> str: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None: ...


class LocalStorage(Storage):
    def __init__(self, root: Path | None = None):
        self.root = Path(root or settings.data_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, local_path: str, key: str) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        if Path(local_path).resolve() != dest.resolve():
            shutil.copy2(local_path, dest)
        return str(dest)

    def fetch(self, key: str, local_path: str) -> str:
        src = self.root / key
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, local_path)
        return local_path

    def url(self, key: str) -> str:
        return f"/files/{key}"

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return [
            str((base / f.name).relative_to(self.root)).replace("\\", "/")
            for f in sorted(base.iterdir())
            if f.is_file()
        ]

    def delete_prefix(self, prefix: str) -> None:
        target = self.root / prefix
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


class S3Storage(Storage):
    def __init__(self, bucket: str, region: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def save(self, local_path: str, key: str) -> str:
        self.client.upload_file(local_path, self.bucket, key)
        return f"s3://{self.bucket}/{key}"

    def fetch(self, key: str, local_path: str) -> str:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, local_path)
        return local_path

    def url(self, key: str, expires: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys += [obj["Key"] for obj in page.get("Contents", [])]
        return keys

    def delete_prefix(self, prefix: str) -> None:
        keys = self.list_keys(prefix)
        if not keys:
            return
        # `delete_objects` acepta hasta 1000 keys por llamada.
        for i in range(0, len(keys), 1000):
            batch = keys[i : i + 1000]
            self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": [{"Key": k} for k in batch]}
            )


def get_storage() -> Storage:
    if settings.s3_bucket:
        return S3Storage(settings.s3_bucket, settings.aws_region)
    return LocalStorage()
