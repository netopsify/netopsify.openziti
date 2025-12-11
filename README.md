# OpenZiti Ansible Collection

The `netopsify.openziti` collection provides a robust, declarative way to manage OpenZiti Overlay Networks using Ansible. 

It is designed to handle complex Day-2 operations, enabling you to define your network as code (NaC) and apply it idempotently.

## Features

*   **Declarative Configuration**: Define Services, Identities, and Policies in simple YAML files.
*   **Idempotency**: Modules check state before making changes, ensuring safe re-runs.
*   **Smart Mode**: Only targets changed resources for faster execution in CI/CD pipelines.
*   **Full Lifecycle**: Create, Update, and Delete support for all major OpenZiti resources.

## Documentation

*   [**Architecture Overview**](docs/ARCHITECTURE.md): Learn how the collection processes your configuration.
*   [**Filter Logic**](docs/FILTERS.md): Understand the `ziti_transform` filter.

## Getting Started

### 1. Installation

Install the collection locally:

```bash
ansible-galaxy collection install netopsify.openziti
```

### 2. Define your Network

Create a directory structure for your definitions:

```
deployments/
├── services/
│   └── my-web-service.yml
└── identities/
    └── my-device.yml
```

**Example `my-web-service.yml`:**

```yaml
services:
  - name: my-web-service
    host:
      address: localhost
      port: 8080
      protocol: tcp
    intercept:
      address: web.service.ziti
      port: 80
      protocol: tcp
    policies:
      bind:
        roles: ['#all'] 
      dial:
        roles: ['#employees']
```

### 3. Run the Playbook

Use the `openziti_infra` role in your playbook:

```yaml
- hosts: localhost
  collections:
    - netopsify.openziti
  tasks:
    - name: Load Definitions
      openziti_loader:
        base_dir: "{{ playbook_dir }}"
        smart_mode: true
      register: ziti_data

    - name: Transform Data
      set_fact:
        ziti_resources: "{{ ziti_data.ziti_deployment | netopsify.openziti.ziti_transform(ziti_data.target_names) }}"

    - name: Apply Infrastructure
      include_role:
        name: netopsify.openziti.openziti_infra
      vars:
        ziti_resources: "{{ ziti_resources }}"
```

## Application
This collection is used by the `openziti_automation` project to manage the entire stack.

## License
MIT
