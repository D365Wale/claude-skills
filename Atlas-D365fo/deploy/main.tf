# Atlas backend on AWS free tier — OpenTofu skeleton.
# Fill deploy/terraform.tfvars, then: tofu init && tofu plan && tofu apply
terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "key_name" {
  type        = string
  description = "Existing EC2 key pair name for SSH"
}

variable "db_password" {
  type      = string
  sensitive = true
}

# --- Backend host (t2.micro, free tier) ---
resource "aws_security_group" "atlas" {
  name        = "atlas-backend"
  description = "Atlas backend: SSH + HTTP(S)"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "atlas" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = "t2.micro" # free tier
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.atlas.id]

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y docker
    systemctl enable --now docker
    # docker run atlas-backend after pushing the image to ECR / pulling here
  EOF

  tags = { Name = "atlas-backend" }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

# --- Database (db.t3.micro, free tier) with pgvector ---
resource "aws_db_instance" "atlas" {
  identifier             = "atlas-pg"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro" # free tier
  allocated_storage      = 20
  db_name                = "atlas"
  username               = "atlas"
  password               = var.db_password
  skip_final_snapshot    = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.atlas.id]
}

output "backend_public_ip" {
  value = aws_instance.atlas.public_ip
}

output "database_endpoint" {
  value = aws_db_instance.atlas.endpoint
}
