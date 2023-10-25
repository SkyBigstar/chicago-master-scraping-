terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

data "digitalocean_ssh_keys" "keys" {
  sort {
    key       = "name"
    direction = "asc"
  }
}

provider "digitalocean" {
  token = file("do_token.txt")
}

resource "digitalocean_droplet" "default" {
  image      = "docker-20-04"
  name       = "chicagocrashes-ng"
  monitoring = true
  region     = "sfo3"
  size       = "s-8vcpu-16gb"
  user_data  = file("provision.sh")
  ssh_keys   = [for key in data.digitalocean_ssh_keys.keys.ssh_keys : key.fingerprint]
}

output "server_ip" {
  value = resource.digitalocean_droplet.default.ipv4_address
}

