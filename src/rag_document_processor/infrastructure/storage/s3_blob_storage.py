from __future__ import annotations

from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError

from rag_document_processor.application.ports.blob_storage import IBlobStorage
from rag_document_processor.core.config import Settings


class S3BlobStorage(IBlobStorage):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session()
        self._bucket_ready = False

    def _client_kwargs(self) -> dict[str, Any]:
        cfg = Config(s3={"addressing_style": "path"}) if self._settings.s3_endpoint_url else Config()
        return {
            "service_name": "s3",
            "endpoint_url": self._settings.s3_endpoint_url,
            "aws_access_key_id": self._settings.s3_access_key_id,
            "aws_secret_access_key": self._settings.s3_secret_access_key,
            "region_name": self._settings.s3_region,
            "config": cfg,
        }

    async def _ensure_bucket(self, client: Any) -> None:
        if self._bucket_ready:
            return
        bucket = self._settings.s3_bucket_name
        try:
            await client.head_bucket(Bucket=bucket)
        except ClientError:
            try:
                await client.create_bucket(Bucket=bucket)
            except ClientError as e:
                # Another process may have created it between head and create.
                code = e.response.get("Error", {}).get("Code", "")
                if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                    raise
        self._bucket_ready = True

    async def put(self, key: str, data: bytes, *, content_type: str) -> str:
        async with self._session.client(**self._client_kwargs()) as client:
            await self._ensure_bucket(client)
            await client.put_object(
                Bucket=self._settings.s3_bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return key

    async def get_bytes(self, key: str) -> bytes:
        async with self._session.client(**self._client_kwargs()) as client:
            await self._ensure_bucket(client)
            obj = await client.get_object(Bucket=self._settings.s3_bucket_name, Key=key)
            body = await obj["Body"].read()
            return body

    async def delete(self, key: str) -> None:
        async with self._session.client(**self._client_kwargs()) as client:
            await self._ensure_bucket(client)
            await client.delete_object(Bucket=self._settings.s3_bucket_name, Key=key)
