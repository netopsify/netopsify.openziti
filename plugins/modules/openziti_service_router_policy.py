#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_service_router_policy
short_description: Manage OpenZiti Service Edge Router Policies
description:
  - Create, update, and delete service edge router policies on an OpenZiti Controller.
  - Controls which services are available on which edge routers.
  - Essential for defining service reachability across the overlay network.
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
  service_roles:
    description:
      - A list of service roles to include in this policy.
      - e.g., ['@my-service', '#all'].
    required: true
    type: list
    elements: str
  edge_router_roles:
    description:
      - A list of edge router roles to include in this policy.
      - e.g., ['@router-01', '#all'].
    required: true
    type: list
    elements: str
  semantic:
    description:
      - The semantic logic to apply when matching roles.
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
- name: Make all services available on all routers
  openziti_service_router_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "all-services-all-routers"
    service_roles: ["#all"]
    edge_router_roles: ["#all"]
    state: present

- name: Restrict High Security Service to Secure Routers
  openziti_service_router_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "high-sec-policy"
    service_roles: ["#high-security"]
    edge_router_roles: ["#secure-routers"]
    semantic: "AllOf"
    state: present

- name: Remove a service router policy
  openziti_service_router_policy:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    policy_name: "deprecated-policy"
    state: absent
'''

RETURN = r'''
policy:
  description: The full dictionary of the service router policy object.
  returned: success
  type: dict
  contains:
    id:
      description: The unique ID of the policy.
      type: str
    name:
      description: The name of the policy.
      type: str
    serviceRoles:
      description: List of service roles associated.
      type: list
    edgeRouterRoles:
      description: List of edge router roles associated.
      type: list
    semantic:
      description: The semantic logic used.
      type: str
'''

import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import (
    OpenZitiClient, OpenZitiServiceRouterPolicyCreate, HAS_DEPS, IMPORT_ERROR
)

def main():
    """
    Main entry point for the OpenZiti Service Edge Router Policy module.
    """
    module = AnsibleModule(
        argument_spec=dict(
            ziti_controller_url=dict(type='str', required=True),
            ziti_username=dict(type='str', required=True),
            ziti_password=dict(type='str', required=True, no_log=True),
            policy_name=dict(type='str', required=True),
            service_roles=dict(type='list', elements='str', required=True),
            edge_router_roles=dict(type='list', elements='str', required=True),
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
    service_roles = module.params['service_roles']
    edge_router_roles = module.params['edge_router_roles']
    semantic = module.params['semantic']
    state = module.params['state']
    validate_certs = module.params['validate_certs']

    result = dict(
        changed=False,
        policy={}
    )

    client = OpenZitiClient(module, url, verify=validate_certs)
    client.login(username, password)

    existing_policy = client.get_service_router_policy_by_name(policy_name)

    if state == 'present':
        if existing_policy:
            # Check for changes
            current_svc_roles = set(existing_policy.serviceRoles or [])
            desired_svc_roles = set(service_roles or [])
            
            current_er_roles = set(existing_policy.edgeRouterRoles or [])
            desired_er_roles = set(edge_router_roles or [])
            
            needs_update = False
            if current_svc_roles != desired_svc_roles:
                needs_update = True
                
            if current_er_roles != desired_er_roles:
                needs_update = True
            
            if existing_policy.semantic != semantic:
                needs_update = True
                
            if needs_update:
                if module.check_mode:
                    result['changed'] = True
                    result['policy'] = existing_policy.dict()
                    module.exit_json(**result)
                
                update_data = OpenZitiServiceRouterPolicyCreate(
                    name=policy_name,
                    serviceRoles=service_roles,
                    edgeRouterRoles=edge_router_roles,
                    semantic=semantic
                )
                client.update_service_router_policy(existing_policy.id, update_data)
                result['changed'] = True
                updated_policy = client.get_service_router_policy_by_name(policy_name)
                result['policy'] = updated_policy.dict()
            else:
                result['policy'] = existing_policy.dict()
        else:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)

            new_policy = OpenZitiServiceRouterPolicyCreate(
                name=policy_name,
                serviceRoles=service_roles,
                edgeRouterRoles=edge_router_roles,
                semantic=semantic
            )
            created_policy = client.create_service_router_policy(new_policy)
            result['changed'] = True
            result['policy'] = created_policy.dict()

    elif state == 'absent':
        if existing_policy:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)
            
            client.delete_service_router_policy(existing_policy.id)
            result['changed'] = True

    module.exit_json(**result)

if __name__ == '__main__':
    main()
