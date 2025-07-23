"""Reusable S3 bucket component."""
from __future__ import annotations

import pulumi
from pulumi import ResourceOptions
from pulumi_aws import s3

__all__ = ["StorageBucket"]


class StorageBucket(pulumi.ComponentResource):
    """Create an S3 bucket whose name is `<prefix>-<stack>`."""

    bucket: s3.BucketV2
    bucket_id: pulumi.Output[str]
    bucket_name: pulumi.Output[str]

    def __init__(
        self,
        name: str,
        prefix: str,
        *,
        force_destroy: bool = True,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("custom:storage:Bucket", name, None, opts)

        child_opts = ResourceOptions(parent=self)
        stack = pulumi.get_stack()

        self.bucket = s3.BucketV2(
            f"{name}-bucket",
            bucket=f"{prefix}-{stack}",
            force_destroy=force_destroy,
            opts=child_opts,
        )

        self.bucket_id = self.bucket.id
        self.bucket_name = self.bucket.bucket

        self.register_outputs({
            "bucket_id": self.bucket_id,
            "bucket_name": self.bucket_name,
        })
