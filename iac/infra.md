# Infrastructure Overview

This document summarizes the AWS resources that the Pulumi program in the `iac` folder currently provisions.

## Global
* **Pulumi Stack**: `test` (creates state file and tracks all resources)

## S3
* **S3 Bucket**: `pulumitestbucket4143-<stack>`
  * Created with `force_destroy=true` so the bucket can be deleted even if objects exist.
  * Exported output: `bucket_name` (bucket ARN).

## Networking (VPC Component)
* **VPC**: `core-vpc` (`10.0.0.0/16`)
  * DNS hostnames & support enabled.
* **Internet Gateway**: `core-igw` – attached to the VPC.

### Public Subnets (2)
| Subnet | CIDR | Public IP on launch | Route Table |
|--------|------|---------------------|-------------|
| `core-public-a` | `10.0.0.0/24` | Yes | `core-public-rt` |
| `core-public-b` | `10.0.1.0/24` | Yes | `core-public-rt` |

* **Route Table** `core-public-rt`
  * Default route `0.0.0.0/0` → Internet Gateway.

### Private Subnets (2)
| Subnet | CIDR | Public IP on launch | Route Table |
|--------|------|---------------------|-------------|
| `core-private-a` | `10.0.2.0/24` | No | `core-private-rt` |
| `core-private-b` | `10.0.3.0/24` | No | `core-private-rt` |

* **Route Table** `core-private-rt`
  * No internet egress (no NAT GW).

### Outputs
* `vpc_id` – ID of the VPC.
* `public_subnet_ids` – list of the two public subnet IDs.
* `private_subnet_ids` – list of the two private subnet IDs.

---
To preview or deploy these resources, run:
```bash
cd iac
pulumi preview   # show changes
pulumi up        # apply
```
