"""Reusable VPC component resource with public and private subnets."""
from typing import List

import pulumi
from pulumi import ResourceOptions
from pulumi_aws import ec2


class Vpc(pulumi.ComponentResource):
    """Create a /16 VPC with two public and two private subnets.

    Private subnets have no internet egress by default (no NAT).
    """

    def __init__(
        self,
        name: str,
        cidr_block: str = "10.0.0.0/16",
        opts: ResourceOptions | None = None,
    ) -> None:
        super().__init__("custom:network:Vpc", name, None, opts)

        child_opts = ResourceOptions(parent=self)

        self.vpc = ec2.Vpc(
            f"{name}-vpc",
            cidr_block=cidr_block,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={"Name": f"{name}-vpc"},
            opts=child_opts,
        )

        igw = ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=self.vpc.id,
            tags={"Name": f"{name}-igw"},
            opts=child_opts,
        )

        azs = ["a", "b"]
        public_subnets: List[ec2.Subnet] = []
        for index, az_suffix in enumerate(azs):
            subnet = ec2.Subnet(
                f"{name}-public-{az_suffix}",
                vpc_id=self.vpc.id,
                cidr_block=f"10.0.{index}.0/24",
                map_public_ip_on_launch=True,
                tags={"Name": f"{name}-public-{az_suffix}"},
                opts=child_opts,
            )
            public_subnets.append(subnet)

        public_rt = ec2.RouteTable(
            f"{name}-public-rt",
            vpc_id=self.vpc.id,
            routes=[
                ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", gateway_id=igw.id)
            ],
            tags={"Name": f"{name}-public-rt"},
            opts=child_opts,
        )
        for subnet in public_subnets:
            ec2.RouteTableAssociation(
                f"{subnet._name}-rta",
                subnet_id=subnet.id,
                route_table_id=public_rt.id,
                opts=child_opts,
            )

        private_subnets: List[ec2.Subnet] = []
        for index, az_suffix in enumerate(azs):
            subnet = ec2.Subnet(
                f"{name}-private-{az_suffix}",
                vpc_id=self.vpc.id,
                cidr_block=f"10.0.{index+2}.0/24",
                map_public_ip_on_launch=False,
                tags={"Name": f"{name}-private-{az_suffix}"},
                opts=child_opts,
            )
            private_subnets.append(subnet)

        private_rt = ec2.RouteTable(
            f"{name}-private-rt",
            vpc_id=self.vpc.id,
            tags={"Name": f"{name}-private-rt"},
            opts=child_opts,
        )
        for subnet in private_subnets:
            ec2.RouteTableAssociation(
                f"{subnet._name}-rta",
                subnet_id=subnet.id,
                route_table_id=private_rt.id,
                opts=child_opts,
            )

        self.vpc_id = self.vpc.id
        self.public_subnet_ids = [s.id for s in public_subnets]
        self.private_subnet_ids = [s.id for s in private_subnets]

        self.register_outputs(
            {
                "vpc_id": self.vpc_id,
                "public_subnet_ids": self.public_subnet_ids,
                "private_subnet_ids": self.private_subnet_ids,
            }
        )
