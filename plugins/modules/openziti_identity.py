#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_identity
short_description: Manage OpenZiti Identities
description:
  - Create, update, and delete identities on an OpenZiti Controller.
  - Supports managing identity roles and types.
  - Allows saving enrollment tokens (JWT) to a local file for onboarding.
options:
  ziti_controller_url:
    description:
      - The URL of the OpenZiti Controller (e.g., https://ziti.example.com:1280).
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
  identity_name:
    description:
      - The name of the identity to manage.
      - Must be unique within the OpenZiti environment.
    required: true
    type: str
  identity_type:
    description:
      - The type of identity.
      - Common types are 'Device', 'User', 'Service'.
    default: Device
    type: str
  role_attributes:
    description:
      - A list of role attributes to assign to the identity.
      - Role attributes are used for policy matching (e.g., '#sales', '#iot').
    type: list
    elements: str
  enrollment_method:
    description:
      - The method to use for enrollment.
      - Currently defaults to 'ott' (One-Time Token).
    default: ott
    type: str
  jwt_output_dir:
    description:
      - The directory where the enrollment JWT file should be saved.
      - If specified, the module will save the JWT to '<jwt_output_dir>/<identity_name>.jwt'.
      - If not specified, the JWT content is returned in the module output but not saved to a file.
    type: path
  state:
    description:
      - The desired state of the identity.
      - If C(present), the identity will be created or updated.
      - If C(absent), the identity will be removed.
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
- name: Create a device identity for a server
  openziti_identity:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    identity_name: "web-server-01"
    identity_type: "Device"
    role_attributes: ["#servers", "#web-hosting"]
    jwt_output_dir: "/opt/openziti/enrollment"
    state: present

- name: Create a user identity
  openziti_identity:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    identity_name: "john.doe"
    identity_type: "User"
    role_attributes: ["#employees"]
    state: present

- name: Remove an identity
  openziti_identity:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    identity_name: "web-server-01"
    state: absent
'''

RETURN = r'''
identity:
  description: The full dictionary of the identity object.
  returned: success
  type: dict
  contains:
    id:
      description: The unique ID of the identity.
      type: str
    name:
      description: The name of the identity.
      type: str
    type:
      description: The type of the identity (e.g., Device).
      type: str
    roleAttributes:
      description: List of role attributes assigned.
      type: list
jwt_file:
  description: The absolute path to the saved JWT file (if jwt_output_dir was provided).
  returned: when jwt_output_dir is set and a JWT is available
  type: str
jwt_content:
  description: The raw string content of the JWT token.
  returned: when a JWT is available (typically on creation or if not enrolled)
  type: str
'''

import os
import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.netopsify.openziti.plugins.module_utils.openziti_common import (
    OpenZitiClient, OpenZitiIdentityCreate, OpenZitiIdentityEnrollment,
    HAS_DEPS, IMPORT_ERROR
)

def main():
    """
    Main entry point for the OpenZiti Identity module.
    """
    module = AnsibleModule(
        argument_spec=dict(
            ziti_controller_url=dict(type='str', required=True),
            ziti_username=dict(type='str', required=True),
            ziti_password=dict(type='str', required=True, no_log=True),
            identity_name=dict(type='str', required=True),
            identity_type=dict(type='str', default='Device'),
            role_attributes=dict(type='list', elements='str'),
            enrollment_method=dict(type='str', default='ott'),
            jwt_output_dir=dict(type='path'),
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
    identity_name = module.params['identity_name']
    identity_type = module.params['identity_type']
    role_attributes = module.params['role_attributes']
    jwt_output_dir = module.params['jwt_output_dir']
    state = module.params['state']
    validate_certs = module.params['validate_certs']

    result = dict(
        changed=False,
        identity={},
        jwt_file=None
    )

    client = OpenZitiClient(module, url, verify=validate_certs)
    
    # Attempt login
    client.login(username, password)

    # Check if identity exists
    existing_identity = client.get_identity_by_name(identity_name)

    if state == 'present':
        if existing_identity:
            # Check for changes
            current_roles = set(existing_identity.roleAttributes or [])
            desired_roles = set(role_attributes or [])
            
            needs_update = False
            if current_roles != desired_roles:
                needs_update = True
                
            if existing_identity.type != identity_type:
                needs_update = True
                
            if needs_update:
                if module.check_mode:
                    result['changed'] = True
                    result['identity'] = existing_identity.dict()
                    module.exit_json(**result)
                
                # We do not pass enrollment for updates usually
                update_data = OpenZitiIdentityCreate(
                    name=identity_name,
                    type=identity_type,
                    roleAttributes=role_attributes,
                    enrollment=OpenZitiIdentityEnrollment(ott=True)
                )
                client.update_identity(existing_identity.id, update_data)
                result['changed'] = True
                updated_identity = client.get_identity_by_name(identity_name)
                result['identity'] = updated_identity.dict()
            else:
                result['identity'] = existing_identity.dict()
            
            # If user requested JWT, we try to fetch it if available (usually only available if not enrolled)
            if jwt_output_dir:
                jwt = client.get_enrollment_jwt(existing_identity.id)
                if jwt:
                    jwt_path = os.path.join(jwt_output_dir, f"{identity_name}.jwt")
                    if not module.check_mode:
                        try:
                            if not os.path.exists(jwt_output_dir):
                                os.makedirs(jwt_output_dir)
                            with open(jwt_path, 'w') as f:
                                f.write(jwt)
                            result['jwt_file'] = jwt_path
                            result['jwt_content'] = jwt
                            # We don't mark changed=True just for file write if identity didn't change,
                            # to stay idempotent regarding the API state.
                        except Exception as e:
                            module.fail_json(msg=f"Failed to write JWT file: {str(e)}")
        else:
            # Identity does not exist, create it
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)

            # Prepare creation data
            enrollment = OpenZitiIdentityEnrollment(ott=True)
            new_identity_data = OpenZitiIdentityCreate(
                name=identity_name,
                type=identity_type,
                roleAttributes=role_attributes,
                enrollment=enrollment
            )
            
            created_identity = client.create_identity(new_identity_data)
            result['changed'] = True
            result['identity'] = created_identity.dict()

            # Handle JWT
            jwt = client.get_enrollment_jwt(created_identity.id)
            if jwt:
                result['jwt_content'] = jwt
                if jwt_output_dir:
                    jwt_path = os.path.join(jwt_output_dir, f"{identity_name}.jwt")
                    try:
                        if not os.path.exists(jwt_output_dir):
                            os.makedirs(jwt_output_dir)
                        with open(jwt_path, 'w') as f:
                            f.write(jwt)
                        result['jwt_file'] = jwt_path
                    except Exception as e:
                        module.fail_json(msg=f"Failed to write JWT file: {str(e)}")

    elif state == 'absent':
        if existing_identity:
            if module.check_mode:
                result['changed'] = True
                module.exit_json(**result)
            
            client.delete_identity(existing_identity.id)
            result['changed'] = True
        else:
            # Already absent
            pass

    module.exit_json(**result)

if __name__ == '__main__':
    main()
