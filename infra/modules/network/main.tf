# Network module — VPC, subnets, IGW, NAT gateway(s), and route tables.
#
# Topology (per design §11.2):
#   • Public subnets   — ALB, NAT gateway EIPs (one per AZ or one shared)
#   • Private-app      — API / backend application services
#   • Private-data     — Mock services and future data-tier workloads
#
# Cost optimisation: `single_nat_gateway = true` (default) creates a single
# NAT gateway in the first AZ.  Set to false for full HA in production.

locals {
  prefix   = "${var.project_name}-${var.environment}"
  az_count = length(var.public_subnet_cidrs)
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ── VPC ────────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.prefix}-vpc"
  }
}

# ── Internet Gateway ────────────────────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.prefix}-igw"
  }
}

# ── Public subnets ──────────────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  count = local.az_count

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.prefix}-public-${count.index + 1}"
    Tier = "public"
  }
}

# ── Private application subnets ─────────────────────────────────────────────────
resource "aws_subnet" "private_app" {
  count = local.az_count

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_app_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${local.prefix}-private-app-${count.index + 1}"
    Tier = "private-app"
  }
}

# ── Private data / integration subnets ─────────────────────────────────────────
resource "aws_subnet" "private_data" {
  count = local.az_count

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_data_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${local.prefix}-private-data-${count.index + 1}"
    Tier = "private-data"
  }
}

# ── Elastic IPs for NAT ─────────────────────────────────────────────────────────
resource "aws_eip" "nat" {
  # One EIP per NAT gateway: 1 (single_nat) or az_count (HA).
  count  = var.single_nat_gateway ? 1 : local.az_count
  domain = "vpc"

  tags = {
    Name = "${local.prefix}-nat-eip-${count.index + 1}"
  }

  depends_on = [aws_internet_gateway.main]
}

# ── NAT Gateways ────────────────────────────────────────────────────────────────
resource "aws_nat_gateway" "main" {
  count = var.single_nat_gateway ? 1 : local.az_count

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "${local.prefix}-nat-${count.index + 1}"
  }

  depends_on = [aws_internet_gateway.main]
}

# ── Public route table (shared across all public subnets) ──────────────────────
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${local.prefix}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count = local.az_count

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ── Private route tables ────────────────────────────────────────────────────────
# One shared table (single_nat) or one per AZ (HA).
resource "aws_route_table" "private" {
  count  = var.single_nat_gateway ? 1 : local.az_count
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name = "${local.prefix}-private-rt-${count.index + 1}"
  }
}

resource "aws_route_table_association" "private_app" {
  count = local.az_count

  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private[var.single_nat_gateway ? 0 : count.index].id
}

resource "aws_route_table_association" "private_data" {
  count = local.az_count

  subnet_id      = aws_subnet.private_data[count.index].id
  route_table_id = aws_route_table.private[var.single_nat_gateway ? 0 : count.index].id
}
