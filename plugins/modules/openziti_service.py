#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_service
short_description: Manage OpenZiti Services
description:
  - Create, update, and delete services on an OpenZiti Controller.
options:
  ziti_controller_url:
    description:
      - The URL of the OpenZiti Controller.
    required: true
    type: str
  ziti_username:
    description:
      - The username for authentication.
    required: true
    type: str
  ziti_password:
    description:
      - The password for authentication.
    required: true
    type: str
  service_name:
    description:
      - The name of the service to manage.
    required: true
    type: str
  role_attributes:
    description:
      - List of role attributes.
    type: list
    elements: str
  configs:
    description:
      - List of config names to associate with the service.
    type: list
    elements: str
  encryption_required:
    description:
      - Whether encryption is required.
    default: true
    type: bool
  state:
    description:
      - Whether the service should exist or not.
    default: present
    choices: [ present, absent ]
    type: str
  validate_certs:
    description:
      - Whether to validate SSL certificates.
    default: true
    type: bool
author:
  - Waqas
'''

EXAMPLES = r'''
- name: Create a service
  openziti_service:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    service_name: "my-service"
    role_attributes: ["my-service.role"]
    configs: ["my-service-host-config"]
    state: present
'''

RETURN = r'''
service:
  description: The service details.
  returned: success
  type: dict
  contains:
    id:
      description: The ID of the service.
      type: str
    name:
      description: The name of the service.
      type: str
'''

import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import OpenZitiClient, OpenZitiServiceCreate, HAS_DEPS, IMPORT_ERROR

def main():
    module = AnsibleModule(
        argument_spec=dict(
            ziti_controller_url=dict(type='str', required=True),
            ziti_username=dict(type='str', required=True),
            ziti_password=dict(type='str', required=True, no_log=True),
            service_name=dict(type='str', required=True),
            role_attributes=dict(type='list', elements='str'),
            configs=dict(type='list', elements='str'),
            encryption_required=dict(type='bool', default=True),
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
    service_name = module.params['service_name']
    role_attributes = module.params['role_attributes']
    config_names = module.params['configs']
    encryption_required = module.params['encryption_required']
    state = module.params['state']
    validate_certs = module.params['validate_certs']

    result = dict(
        changed=False,
        service={}
    )

    client = OpenZitiClient(module, url, verify=validate_certs)
    client.login(username, password)

    existing_service = client.get_service_by_name(service_name)

    if state == 'present':
        # Resolve config IDs
        config_ids = []
        if config_names:
            for c_name in config_names:
                c = client.get_config_by_name(c_name)
                if c:
                    config_ids.append(c.id)
                else:
                    module.fail_json(msg=f"Config '{c_name}' not found.")

        if existing_service:
            # TODO: Update logic
            result['service'] = existing_service.dict()
        else:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)

            new_service = OpenZitiServiceCreate(
                name=service_name,
                roleAttributes=role_attributes,
                configs=config_ids,
                encryptionRequired=encryption_required
            )
            created_service = client.create_service(new_service)
            result['changed'] = True
            result['service'] = created_service.dict()

    elif state == 'absent':
        if existing_service:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)
            
            client.delete_service(existing_service.id)
            result['changed'] = True

    module.exit_json(**result)

if __name__ == '__main__':
    main()
