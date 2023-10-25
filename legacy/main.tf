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

resource "digitalocean_droplet" "n8n" {
  image     = "debian-11-x64"
  name      = "n8n-chicagocrashes"
  region    = "sfo3"
  size      = "s-2vcpu-2gb"
  user_data = file("provision.sh")
  ssh_keys  = [for key in data.digitalocean_ssh_keys.keys.ssh_keys : key.fingerprint]
}

output "server_ip" {
  value = resource.digitalocean_droplet.n8n.ipv4_address
}

