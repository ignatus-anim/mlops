"""Reusable EC2 instance component."""
from __future__ import annotations

from typing import Optional

import pulumi
from pulumi import ResourceOptions
from pulumi_aws import ec2, iam

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
        instance_type: str = "t3.medium",
        key_name: Optional[str] = "lynx-key",
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("custom:compute:Instance", name, None, opts)

        child_opts = ResourceOptions(parent=self)

        # IAM role for S3 access
        role = iam.Role(
            f"{name}-role",
            assume_role_policy="""{
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"}
                }]
            }""",
            opts=child_opts,
        )

        policy = iam.RolePolicy(
            f"{name}-s3-policy",
            role=role.id,
            policy="""{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket", "s3:PutObject", "s3:DeleteObject"],
                    "Resource": ["arn:aws:s3:::mlops-bucket0982", "arn:aws:s3:::mlops-bucket0982/*"]
                }]
            }""",
            opts=child_opts,
        )

        instance_profile = iam.InstanceProfile(
            f"{name}-profile",
            role=role.name,
            opts=child_opts,
        )

        sg = ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Allow SSH and application ports",
            ingress=[
                # SSH
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=22, to_port=22, cidr_blocks=["0.0.0.0/0"]),
                # MLflow UI
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=5000, to_port=5000, cidr_blocks=["0.0.0.0/0"]),
                # Airflow UI
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=8080, to_port=8080, cidr_blocks=["0.0.0.0/0"]),
                # Production inference backend
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=6001, to_port=6001, cidr_blocks=["0.0.0.0/0"]),
                # Candidate inference backend
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=6002, to_port=6002, cidr_blocks=["0.0.0.0/0"]),
                # Nginx router
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=7000, to_port=7000, cidr_blocks=["0.0.0.0/0"]),
                # Frontend
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=6500, to_port=6500, cidr_blocks=["0.0.0.0/0"]),
                # Flower (optional)
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=5555, to_port=5555, cidr_blocks=["0.0.0.0/0"]),
                # Prometheus
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=9090, to_port=9090, cidr_blocks=["0.0.0.0/0"]),
                # Grafana
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=3000, to_port=3000, cidr_blocks=["0.0.0.0/0"]),
                # Node Exporter
                ec2.SecurityGroupIngressArgs(protocol="tcp", from_port=9100, to_port=9100, cidr_blocks=["0.0.0.0/0"])
            ],
            egress=[
                ec2.SecurityGroupEgressArgs(protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"])
            ],
            tags={"Name": f"{name}-sg"},
            opts=child_opts,
        )

        ami = ec2.get_ami(
            most_recent=True,
            owners=["099720109477"],  # Canonical
            filters=[ec2.GetAmiFilterArgs(name="name", values=["ubuntu/images/hvm-ssd/ubuntu-*-amd64-server-*"])],
        )

        user_data = """#!/bin/bash
apt update -y
apt install -y docker.io git
systemctl start docker
systemctl enable docker
usermod -a -G docker ubuntu
"""

        self.instance = ec2.Instance(
            f"{name}-ec2",
            instance_type=instance_type,
            ami=ami.id,
            subnet_id=subnet_id,
            vpc_security_group_ids=[sg.id],
            associate_public_ip_address=True,
            key_name=key_name,
            user_data=user_data,
            iam_instance_profile=instance_profile.name,
            tags={"Name": f"{name}-ec2"},
            opts=child_opts,
        )

        self.public_ip = self.instance.public_ip
        self.instance_id = self.instance.id

        self.register_outputs({"instance_id": self.instance_id, "public_ip": self.public_ip})
