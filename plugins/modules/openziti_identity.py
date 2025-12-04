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
  - Supports saving enrollment JWTs to local files.
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
  identity_name:
    description:
      - The name of the identity to manage.
    required: true
    type: str
  identity_type:
    description:
      - The type of identity (e.g., Device, User, Service).
    default: Device
    type: str
  role_attributes:
    description:
      - List of role attributes to assign to the identity.
    type: list
    elements: str
  enrollment_method:
    description:
      - The enrollment method to use.
    default: ott
    type: str
  jwt_output_dir:
    description:
      - Directory to save the enrollment JWT file.
      - If not specified, the JWT is not saved to a file, but returned in the module output.
    type: path
  state:
    description:
      - Whether the identity should exist or not.
    default: present
    choices: [ present, absent ]
    type: str
author:
  - Waqas
'''

EXAMPLES = r'''
- name: Create a device identity
  openziti_identity:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    identity_name: "my-device"
    identity_type: "Device"
    role_attributes: ["my-device.hosts"]
    jwt_output_dir: "/tmp/tokens"
    state: present

- name: Remove an identity
  openziti_identity:
    ziti_controller_url: "https://ziti.example.com"
    ziti_username: "admin"
    ziti_password: "password"
    identity_name: "my-device"
    state: absent
'''

RETURN = r'''
identity:
  description: The identity details.
  returned: success
  type: dict
  contains:
    id:
      description: The ID of the identity.
      type: str
    name:
      description: The name of the identity.
      type: str
    type:
      description: The type of the identity.
      type: str
jwt_file:
  description: Path to the saved JWT file (if jwt_output_dir was specified).
  returned: when jwt_output_dir is set and identity is created
  type: str
jwt_content:
  description: The content of the JWT token.
  returned: when identity is created
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
            # Identity exists
            # TODO: Implement update logic if needed (e.g. role attributes)
            # For now, we assume if it exists, it's fine.
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
                            # If we just wrote the file, is that a change? 
                            # Usually file creation is a change, but the identity itself didn't change.
                            # We can mark changed=True if we want to reflect file creation.
                            # But strictly speaking the module manages the identity.
                            # Let's say if we wrote the file, it's a change? 
                            # Maybe not, unless the identity was created. 
                            # But if the user wants the file, and it wasn't there...
                            # Let's stick to identity changes for now.
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
