"""Pulumi reusable components package.

This package groups all custom ComponentResources so they can be imported as:

    from iac.components import Vpc, StorageBucket, ComputeInstance
"""
from .vpc import Vpc  # noqa: F401
from .s3 import StorageBucket  # noqa: F401
from .ec2 import ComputeInstance  # noqa: F401
