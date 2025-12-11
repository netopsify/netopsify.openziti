# Filter Plugin: `ziti_transform`

The `ziti_transform` filter is a specialized Jinja2 filter included in this collection. Its purpose is to translate the "Service-Centric" deployment definitions into the flat, resource-centric lists that Ansible modules require.

## Usage

In your playbook, you typically pass the output of `openziti_loader` to this filter:

```yaml
- name: Transform Data
  set_fact:
    ziti_resources: "{{ ziti_data.ziti_deployment | netopsify.openziti.ziti_transform(ziti_data.target_names) }}"
```

## Transformation Logic

The filter performs several key normalizations and expansions:

### 1. Services & Configs
When a Service is defined with inline `host` or `intercept` configurations, the filter splits these into separate objects:
*   **Input**: A single Service dict with `host: {...}`.
*   **Output**: 
    1.  A `host.v1` Config object named `<service_name>-host-v1`.
    2.  A Service object referencing that Config ID.

### 2. Policies
Policies defined inside a service are expanded into standalone Policy objects.
*   **Bind Policy**: Creates a policy named `<service_name>-bind`.
*   **Dial Policy**: Creates a policy named `<service_name>-dial`.
*   **Router Policy**: Creates a `service-edge-router-policy` named `<service_name>-router`.

### 3. Role Auto-Generation
To simplify policy management, the filter automatically handles role attributes:
*   **Services**: Automatically get a role attribute `#{service_name}`.
*   **Policies**: Are configured to use these auto-generated attributes to link valid services and identities.

## Smart Mode Integration

The filter accepts an optional second argument: `target_names`.

*   **If `target_names` is provided**: The filter **only** generates output objects for resources whose names are in this list. This allows the playbook to run in "Smart Mode", skipping thousands of unchanged resources and drastically reducing execution time.
*   **If `target_names` is empty/null**: All resources are processed (Full Run).
