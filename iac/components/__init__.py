"""Pulumi reusable components package.

This package groups all custom ComponentResources so they can be imported as:

    from iac.components import Vpc, ComputeInstance
"""
from .vpc import Vpc  # noqa: F401
from .ec2 import ComputeInstance  # noqa: F401
