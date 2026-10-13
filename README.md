# ansible-k8s-provisioning

Infrastructure as code project using Ansible to provision a production-ready Kubernetes cluster on local Multipass virtual machines.

## Overview

Complete automation of a Kubernetes cluster lifecycle. Powered by kubeadm, Ansible playbooks, and a custom Multipass connection plugin.

Designed for developers and DevOps engineers who need a real multi-node Kubernetes environment locally, without relying on cloud providers or simplified distributions like Minikube or K3s. 

## Features

Clusters come pre-configured with Flannel networking, Ingress NGINX, and a default StorageClass, making them ready for real workload testing. The project provides three core operations:

- Cluster creation
	- Create VMs, configure one control plane, configure many workers and join them to the cluster.
- Worker node scale up
	- Create, configure and join a new VM worker to the cluster to scale up workers resources.
- Worker node scale down
	- Gracefully remove a worker from the current cluster to scale down workers resources.

Technical features: 
- Custom Multipass connection plugin — Ansible communicates directly with VMs through multipass exec, no SSH configuration needed
- Idempotent playbooks — Safe to re-run without breaking existing cluster state
- Graceful node removal — Workers are cordoned, drained, then deleted from the cluster before VM cleanup   
- Dynamic inventory — Inventory is generated at runtime based on actual VM state
- Configurable resources — CPU, memory, disk, Kubernetes version, all defined in a single config file 

## Prerequisites

Ensure the following are installed: 
- Multipass (For VM management)
- Ansible (To run playbooks)

Currently tested on macOS. Linux support is planned. 

## Quick Start

```bash
git clone https://github.com/YannGhistelinck/ansible-k8s-provisioning.git
cd ansible-k8s-provisioning

# Copy and edit cluster settings
cp vars/cluster-config.yml.example vars/cluster-config.yml
vi vars/cluster-config.yml

# Create the cluster
./run-cluster.sh

# Verify
multipass shell test-cplane
kubectl get nodes
```

## Configuration

All cluster settings are defined in `vars/cluster-config.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `cluster_name` | Prefix used for VM naming | `test` |
| `worker_count` | Number of worker nodes to create | `2` |
| `control_plane.cpus` | vCPUs allocated to the control plane | `2` |
| `control_plane.memory` | RAM allocated to the control plane | `2G` |
| `control_plane.disk` | Disk size for the control plane | `20G` |
| `worker.cpus` | vCPUs allocated to each worker | `1` |
| `worker.memory` | RAM allocated to each worker | `1.5G` |
| `worker.disk` | Disk size for each worker | `15G` |
| `ubuntu_version` | Ubuntu image used by Multipass | `22.04` |
| `network_interface` | Host network interface for VM bridging | `en0` |
| `pod_network_cidr` | Internal IP range for pods (Flannel) | `10.244.0.0/16` |
| `kubernetes_version` | Kubernetes version to install | `1.31` |
| `flannel_version` | Flannel CNI version | `v0.26.1` |
| `traefik_chart_version` | Traefik ingress controller Helm chart version | `41.7.1` |
| `local_path_provisioner_version` | Rancher local-path-provisioner version | `v0.0.26` |

## Usage

### Create a cluster

Provisions the control plane and worker VMs, installs Kubernetes, and configures the cluster.

```bash
./run-cluster.sh
```

Or directly with Ansible:

```bash
ansible-playbook create-cluster.yml
```

### Add a worker node

Adds a new worker to an existing cluster. The new worker automatically gets the next available number.

```bash
./run-add-worker.sh -c <cluster_name>

# Example
./run-add-worker.sh -c test
```

### Remove a worker node

Removes the worker with the highest index. The node is gracefully drained before deletion.

```bash
./run-remove-worker.sh -c <cluster_name>

# Example
./run-remove-worker.sh -c test
```

### Destroy the cluster

Deletes all VMs and cleans up the inventory file. Prompts for confirmation before proceeding.

```bash
./cleanup-cluster.sh
```

## Project Structure
