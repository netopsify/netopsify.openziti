#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_config
short_description: Manage OpenZiti Service Configurations
description:
  - Create, update, and delete service configurations on an OpenZiti Controller.
  - Supports various config types such as 'host.v1' and 'intercept.v1'.
options:
  ziti_controller_url:
    description:
      - The URL of the OpenZiti Controller.
    required: true
    type: str
  ziti_username:
    description:
      - The username for authentication with the OpenZiti Controller.
    required: true
    type: str
  ziti_password:
    description:
      - The password for authentication with the OpenZiti Controller.
    required: true
    type: str
  config_name:
    description:
      - The name of the configuration to manage.
      - Must be unique within the OpenZiti environment.
    required: true
    type: str
  config_type_name:
    description:
      - The name of the config type schema.
      - Common examples include 'host.v1', 'intercept.v1', 'ziti-tunneler-client.v1'.
    required: true
    type: str
  data:
    description:
      - The configuration data payload as a dictionary.
      - The structure depends on the selected C(config_type_name).
    required: true
    type: dict
  state:
    description:
      - The desired state of the configuration.
      - If C(present), the configuration will be created or updated.
      - If C(absent), the configuration will be removed.
    default: present
    choices: [ present, absent ]
    type: str
  validate_certs:
    description:
      - Whether to validate SSL certificates when connecting to the controller.
    default: true
    type: bool
author:
  - Waqas (@netopsify)
'''

EXAMPLES = r'''
- name: Create a host config for a service
  openziti_config:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    config_name: "web-app-host-config"
    config_type_name: "host.v1"
    data:
      protocol: "tcp"
      address: "localhost"
      port: 8080
    state: present

- name: Create an intercept config to map a service to a local address
  openziti_config:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    config_name: "web-app-intercept-config"
    config_type_name: "intercept.v1"
    data:
      protocols: ["tcp"]
      addresses: ["web.service.ziti"]
      portRanges:
        - low: 80
          high: 80
    state: present
'''

RETURN = r'''
config:
  description: The detailed dictionary of the configuration object.
  returned: success
  type: dict
  contains:
    id:
      description: The unique ID assigned to the configuration.
      type: str
    name:
      description: The name of the configuration.
      type: str
    configTypeId:
      description: The ID of the configuration type this config adheres to.
      type: str
    data:
      description: The actual configuration data payload.
      type: dict
'''

import traceback
import json
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import OpenZitiClient, OpenZitiConfig, OpenZitiConfigCreate, HAS_DEPS, IMPORT_ERROR


def main():
    """
    Main entry point for the OpenZiti Config module.
    """
    module = AnsibleModule(
        argument_spec=dict(
            ziti_controller_url=dict(type='str', required=True),
            ziti_username=dict(type='str', required=True),
            ziti_password=dict(type='str', required=True, no_log=True),
            config_name=dict(type='str', required=True),
            config_type_name=dict(type='str', required=True),
            data=dict(type='dict', required=True),
            state=dict(type='str', default='present', choices=['present', 'absent']),
            validate_certs=dict(type='bool', default=True),
        ),
        supports_check_mode=True
    )

    if not HAS_DEPS:
        module.fail_json(msg="Missing required dependencies: %s" % IMPORT_ERROR)

    url = module.params['ziti_controller_url']
    username = module.params['ziti_username']
    password = module.params['ziti_password']
    config_name = module.params['config_name']
    config_type_name = module.params['config_type_name']
    data = module.params['data']
    state = module.params['state']
    validate_certs = module.params['validate_certs']

    result = dict(
        changed=False,
        config={}
    )

    client = OpenZitiClient(module, url, verify=validate_certs)
    client.login(username, password)

    existing_config = client.get_config_by_name(config_name)

    if state == 'present':
        # Resolve config type ID from the provided name
        config_type_id = client.get_config_type_by_name(config_type_name)
        if not config_type_id:
            module.fail_json(msg=f"Config Type '{config_type_name}' not found on the controller.")

        if existing_config:
            # Check if update is needed by comparing data payloads
            # We sort keys to ensure improved consistency in comparison
            current_data_str = json.dumps(existing_config.data, sort_keys=True)
            new_data_str = json.dumps(data, sort_keys=True)
            
            if current_data_str != new_data_str:
                if module.check_mode:
                    result['changed'] = True
                    module.exit_json(**result)

                new_config = OpenZitiConfigCreate(
                    name=config_name,
                    configTypeId=config_type_id,
                    data=data
                )
                client.update_config(existing_config.id, new_config)
                result['changed'] = True
                result['config'] = new_config.dict()
            else:
                result['config'] = existing_config.dict()

        else:
            # Create new config
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)

            new_config = OpenZitiConfigCreate(
                name=config_name,
                configTypeId=config_type_id,
                data=data
            )
            created_config = client.create_config(new_config)
            result['changed'] = True
            result['config'] = created_config.dict()

    elif state == 'absent':
        if existing_config:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)
            
            client.delete_config(existing_config.id)
            result['changed'] = True

    module.exit_json(**result)

if __name__ == '__main__':
    main()
