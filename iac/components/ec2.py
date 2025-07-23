"""Reusable EC2 instance component."""
from __future__ import annotations

from typing import Optional

import pulumi
from pulumi import ResourceOptions
from pulumi_aws import ec2

__all__ = ["ComputeInstance"]


class ComputeInstance(pulumi.ComponentResource):
    """Spin up a simple Amazon Linux 2 EC2 instance in a given subnet."""

    instance: ec2.Instance
    public_ip: pulumi.Output[str]
    instance_id: pulumi.Output[str]

    def __init__(
        self,
        name: str,
        *,
        subnet_id: pulumi.Input[str],
        vpc_id: pulumi.Input[str],
        instance_type: str = "t3.micro",
        key_name: Optional[str] = None,
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("custom:compute:Instance", name, None, opts)

        child_opts = ResourceOptions(parent=self)

        sg = ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Allow SSH",
            ingress=[
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=22, to_port=22, cidr_blocks=["0.0.0.0/0"])
            ],
            egress=[
                ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"])
            ],
            tags={"Name": f"{name}-sg"},
            opts=child_opts,
        )

        ami = ec2.get_ami(
            most_recent=True,
            owners=["amazon"],
            filters=[ec2.GetAmiFilterArgs(name="name", values=["amzn2-ami-hvm-*-x86_64-gp2"])],
        )

        self.instance = ec2.Instance(
            f"{name}-ec2",
            instance_type=instance_type,
            ami=ami.id,
            subnet_id=subnet_id,
            vpc_security_group_ids=[sg.id],
            associate_public_ip_address=True,
            key_name=key_name,
            tags={"Name": f"{name}-ec2"},
            opts=child_opts,
        )

        self.public_ip = self.instance.public_ip
        self.instance_id = self.instance.id

        self.register_outputs({"instance_id": self.instance_id, "public_ip": self.public_ip})
