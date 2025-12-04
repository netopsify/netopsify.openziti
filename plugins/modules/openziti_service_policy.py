#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_service_policy
short_description: Manage OpenZiti Service Policies
description:
  - Create, update, and delete service policies on an OpenZiti Controller.
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
  policy_name:
    description:
      - The name of the policy.
    required: true
    type: str
  policy_type:
    description:
      - The type of policy (Dial or Bind).
    required: true
    choices: [ Dial, Bind ]
    type: str
  service_roles:
    description:
      - List of service roles (e.g., @serviceName or #attribute).
    required: true
    type: list
    elements: str
  identity_roles:
    description:
      - List of identity roles (e.g., @identityName or #attribute).
    required: true
    type: list
    elements: str
  semantic:
    description:
      - The semantic logic (AnyOf or AllOf).
    default: AnyOf
    choices: [ AnyOf, AllOf ]
    type: str
  state:
    description:
      - Whether the policy should exist or not.
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
- name: Create a dial policy
  openziti_service_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "my-dial-policy"
    policy_type: "Dial"
    service_roles: ["@my-service"]
    identity_roles: ["#my-device.hosts"]
    state: present
'''

RETURN = r'''
policy:
  description: The policy details.
  returned: success
  type: dict
  contains:
    id:
      description: The ID of the policy.
      type: str
    name:
      description: The name of the policy.
      type: str
'''

import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import OpenZitiClient, OpenZitiServicePolicyCreate, HAS_DEPS, IMPORT_ERROR

def main():
    module = AnsibleModule(
        argument_spec=dict(
            ziti_controller_url=dict(type='str', required=True),
            ziti_username=dict(type='str', required=True),
            ziti_password=dict(type='str', required=True, no_log=True),
            policy_name=dict(type='str', required=True),
            policy_type=dict(type='str', required=True, choices=['Dial', 'Bind']),
            service_roles=dict(type='list', elements='str', required=True),
            identity_roles=dict(type='list', elements='str', required=True),
            semantic=dict(type='str', default='AnyOf', choices=['AnyOf', 'AllOf']),
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
    policy_name = module.params['policy_name']
    policy_type = module.params['policy_type']
    service_roles = module.params['service_roles']
    identity_roles = module.params['identity_roles']
    semantic = module.params['semantic']
    state = module.params['state']
    validate_certs = module.params['validate_certs']

    result = dict(
        changed=False,
        policy={}
    )

    client = OpenZitiClient(module, url, verify=validate_certs)
    client.login(username, password)

    existing_policy = client.get_service_policy_by_name(policy_name)

    if state == 'present':
        if existing_policy:
            # TODO: Update logic
            result['policy'] = existing_policy.dict()
        else:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)

            new_policy = OpenZitiServicePolicyCreate(
                name=policy_name,
                type=policy_type,
                serviceRoles=service_roles,
                identityRoles=identity_roles,
                semantic=semantic
            )
            created_policy = client.create_service_policy(new_policy)
            result['changed'] = True
            result['policy'] = created_policy.dict()

    elif state == 'absent':
        if existing_policy:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)
            
            client.delete_service_policy(existing_policy.id)
            result['changed'] = True

    module.exit_json(**result)

if __name__ == '__main__':
    main()
