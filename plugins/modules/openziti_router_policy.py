#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_router_policy
short_description: Manage OpenZiti Edge Router Policies
description:
  - Create, update, and delete edge router policies on an OpenZiti Controller.
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
  edge_router_roles:
    description:
      - List of edge router roles.
    required: true
    type: list
    elements: str
  identity_roles:
    description:
      - List of identity roles.
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
- name: Create a router policy
  openziti_router_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "my-router-policy"
    edge_router_roles: ["#all"]
    identity_roles: ["#all"]
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
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import (
    OpenZitiClient, OpenZitiRouterPolicyCreate, HAS_DEPS, IMPORT_ERROR
)

def main():
    module = AnsibleModule(
        argument_spec=dict(
            ziti_controller_url=dict(type='str', required=True),
            ziti_username=dict(type='str', required=True),
            ziti_password=dict(type='str', required=True, no_log=True),
            policy_name=dict(type='str', required=True),
            edge_router_roles=dict(type='list', elements='str', required=True),
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
    edge_router_roles = module.params['edge_router_roles']
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

    existing_policy = client.get_router_policy_by_name(policy_name)

    if state == 'present':
        if existing_policy:
            # TODO: Update logic
            result['policy'] = existing_policy.dict()
        else:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)

            new_policy = OpenZitiRouterPolicyCreate(
                name=policy_name,
                edgeRouterRoles=edge_router_roles,
                identityRoles=identity_roles,
                semantic=semantic
            )
            created_policy = client.create_router_policy(new_policy)
            result['changed'] = True
            result['policy'] = created_policy.dict()

    elif state == 'absent':
        if existing_policy:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)
            
            client.delete_router_policy(existing_policy.id)
            result['changed'] = True

    module.exit_json(**result)

if __name__ == '__main__':
    main()
