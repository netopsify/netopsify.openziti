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
  - Policies control which identities can 'Dial' or 'Bind' specific services.
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
  policy_name:
    description:
      - The name of the policy.
      - Must be unique within the OpenZiti environment.
    required: true
    type: str
  policy_type:
    description:
      - The type of policy.
      - 'Dial': Allows identities to access the service.
      - 'Bind': Allows identities to host (provide) the service.
    required: true
    choices: [ Dial, Bind ]
    type: str
  service_roles:
    description:
      - A list of service roles included in this policy.
      - Can be specific service names (prefixed with '@') or role attributes (prefixed with '#').
      - e.g., ['@my-service'] or ['#all-services'].
    required: true
    type: list
    elements: str
  identity_roles:
    description:
      - A list of identity roles included in this policy.
      - Can be specific identity names (prefixed with '@') or role attributes (prefixed with '#').
      - e.g., ['@my-device'] or ['#sales-devices'].
    required: true
    type: list
    elements: str
  semantic:
    description:
      - The semantic logic to apply when matching roles.
      - 'AnyOf': Match if any attribute matches.
      - 'AllOf': Match only if all attributes match.
    default: AnyOf
    choices: [ AnyOf, AllOf ]
    type: str
  state:
    description:
      - The desired state of the policy.
      - If C(present), the policy will be created or updated.
      - If C(absent), the policy will be removed.
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
- name: Create a Dial policy for a specific service and identity
  openziti_service_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "web-app-dial-policy"
    policy_type: "Dial"
    service_roles: ["@web-service"]
    identity_roles: ["@laptop-01"]
    state: present

- name: Create a Bind policy using role attributes
  openziti_service_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "web-app-bind-policy"
    policy_type: "Bind"
    service_roles: ["#web-services"]
    identity_roles: ["#web-hosts"]
    semantic: "AnyOf"
    state: present

- name: Delete a policy
  openziti_service_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "old-policy"
    state: absent
'''

RETURN = r'''
policy:
  description: The full dictionary of the service policy object.
  returned: success
  type: dict
  contains:
    id:
      description: The unique ID of the policy.
      type: str
    name:
      description: The name of the policy.
      type: str
    type:
      description: The type of policy (Dial or Bind).
      type: str
    serviceRoles:
      description: List of service roles associated.
      type: list
    identityRoles:
      description: List of identity roles associated.
      type: list
    semantic:
      description: The semantic logic used.
      type: str
'''

import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import OpenZitiClient, OpenZitiServicePolicyCreate, HAS_DEPS, IMPORT_ERROR

def main():
    """
    Main entry point for the OpenZiti Service Policy module.
    """
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
            # Check for changes
            current_svc_roles = set(existing_policy.serviceRoles or [])
            desired_svc_roles = set(service_roles or [])
            
            current_id_roles = set(existing_policy.identityRoles or [])
            desired_id_roles = set(identity_roles or [])
            
            needs_update = False
            if current_svc_roles != desired_svc_roles:
                needs_update = True
                
            if current_id_roles != desired_id_roles:
                needs_update = True
            
            if existing_policy.type != policy_type:
                needs_update = True
                
            if existing_policy.semantic != semantic:
                needs_update = True
                
            if needs_update:
                if module.check_mode:
                    result['changed'] = True
                    result['policy'] = existing_policy.dict()
                    module.exit_json(**result)
                
                update_data = OpenZitiServicePolicyCreate(
                    name=policy_name,
                    type=policy_type,
                    serviceRoles=service_roles,
                    identityRoles=identity_roles,
                    semantic=semantic
                )
                client.update_service_policy(existing_policy.id, update_data)
                result['changed'] = True
                updated_policy = client.get_service_policy_by_name(policy_name)
                result['policy'] = updated_policy.dict()
            else:
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
