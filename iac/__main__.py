"""An AWS Python Pulumi program"""

import pulumi

from components import ComputeInstance, Vpc


# Create a basic VPC using our reusable component
vpc = Vpc('core')

pulumi.export('vpc_id', vpc.vpc_id)
pulumi.export('public_subnet_ids', vpc.public_subnet_ids)
pulumi.export('private_subnet_ids', vpc.private_subnet_ids)

# Launch an EC2 instance in the first public subnet
instance = ComputeInstance(
    'web',
    subnet_id=vpc.public_subnet_ids[0],
    vpc_id=vpc.vpc_id,
    instance_type='t3.medium',
)

pulumi.export('ec2_instance_id', instance.instance_id)
pulumi.export('ec2_public_ip', instance.public_ip)
