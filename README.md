# Ansible Collection: `netopsify.openziti`

This document provides technical documentation for the custom `netopsify.openziti` Ansible Collection.

## 📦 Modules

### 1. `openziti_identity`
Manages the lifecycle of OpenZiti Identities.

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `ziti_controller_url` | String | **Yes** | - | URL of the OpenZiti Controller. |
| `ziti_username` | String | **Yes** | - | Admin username. |
| `ziti_password` | String | **Yes** | - | Admin password. |
| `identity_name` | String | **Yes** | - | Name of the identity. |
| `identity_type` | String | No | `Device` | `Device`, `User`, or `Service`. |
| `role_attributes` | List | No | `[]` | List of role attributes (e.g., `["#admins"]`). |
| `enrollment_method` | String | No | `ott` | Enrollment method (`ott`, `updb`, `ottca`). |
| `state` | String | No | `present` | `present` or `absent`. |

### 2. `openziti_service`
Manages OpenZiti Services.

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `service_name` | String | **Yes** | - | Name of the service. |
| `role_attributes` | List | No | `[]` | List of role attributes. |
| `configs` | List | No | `[]` | List of **Config IDs** to associate. |
| `encryption_required` | Bool | No | `true` | Require end-to-end encryption. |
| `state` | String | No | `present` | `present` or `absent`. |

### 3. `openziti_config`
Manages Configuration objects (Host.v1, Intercept.v1).

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `config_name` | String | **Yes** | - | Name of the config. |
| `config_type_name` | String | **Yes** | - | Type (e.g., `host.v1`, `intercept.v1`). |
| `data` | Dict | **Yes** | - | JSON/Dict payload for the config. |

### 4. `openziti_service_policy`
Manages Bind and Dial policies.

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `policy_name` | String | **Yes** | - | Name of the policy. |
| `policy_type` | String | **Yes** | - | `Bind` or `Dial`. |
| `service_roles` | List | **Yes** | - | Roles of services to match. |
| `identity_roles` | List | **Yes** | - | Roles of identities to match. |
| `semantic` | String | No | `AnyOf` | `AnyOf` or `AllOf`. |

---

## 🧩 Roles

### `openziti_infra`
This is the **Orchestrator Role**. It does not take direct parameters but expects specific variables to be populated (usually by the `ziti_transform` filter).

**Expected Variables**:
*   `openziti_services`: List of service dicts.
*   `openziti_configs`: List of config dicts.
*   `openziti_service_policies`: List of policy dicts.
*   `openziti_router_policies`: List of router policy dicts.

### `openziti_identity`
Dedicated role for managing identities.
**Expected Variables**:
*   `openziti_identities`: List of identity dicts.

---

## 🔌 Plugins

### `ziti_transform` (Filter)
**File**: `plugins/filter/openziti_filters.py`

This filter is responsible for the **Business Logic** of the automation.
1.  **Input**: Takes the hierarchical `ziti_deployment` dictionary.
2.  **Processing**:
    *   Iterates over Services and Identities.
    *   Generates implicit Config names (e.g., `<svc>-host-v1`).
    *   Generates implicit Policy names (e.g., `<svc>-bind`).
    *   Strips `#` prefixes from role attributes.
    *   Propagates `state: absent` to all child resources.
3.  **Output**: Returns a dictionary containing flat lists for the `openziti_infra` and `openziti_identity` roles.

---

## 👨‍💻 Development Guide

### How to Add a New Module
1.  **Define Pydantic Model**: Add the data model to `plugins/module_utils/openziti_common.py`.
2.  **Add API Methods**: Add `create_...`, `get_...`, `delete_...` methods to the `OpenZitiClient` class in `openziti_common.py`.
3.  **Create Module**: Create a new file in `plugins/modules/` (copy an existing one like `openziti_service.py` as a template).
4.  **Update Role**: Add a task to `roles/openziti_infra/tasks/main.yml` to utilize the new module.
