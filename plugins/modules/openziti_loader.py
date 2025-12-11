#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_loader
short_description: OpenZiti Deployment Definition Loader
description:
  - Scans a directory structure for OpenZiti YAML definitions.
  - Merges multiple YAML files into a single deployment data structure.
  - Implements **Smart Mode** to optimize deployments by only targeting changed resources.
  - Supports git integration to detect changed and deleted files for Smart Mode.
options:
  base_dir:
    description:
      - The absolute path to the base directory containing the 'deployments' folder.
      - The module looks for 'deployments/services' and 'deployments/identities' inside this path.
    required: true
    type: path
  smart_mode:
    description:
      - Enable Smart Mode optimization.
      - If True, the module scans git history to identify changed files.
      - Only resources defined in changed files will be returned in 'target_names'.
      - Deleted files are recovered from git history to mark resources as 'absent'.
    type: bool
    default: false
author:
  - Waqas (@netopsify)
'''

EXAMPLES = r'''
- name: Load all definitions (Full Mode)
  netopsify.openziti.openziti_loader:
    base_dir: "{{ playbook_dir }}"
    smart_mode: false
  register: ziti_data

- name: Load only changed definitions (Smart Mode)
  netopsify.openziti.openziti_loader:
    base_dir: "{{ playbook_dir }}"
    smart_mode: true
  register: ziti_smart_data

- name: Use loaded data
  debug:
    msg: "Targeting services: {{ ziti_smart_data.target_names }}"
'''

RETURN = r'''
ziti_deployment:
  description: The fully merged dictionary of all deployment definitions.
  returned: always
  type: dict
target_names:
  description: 
    - A list of the names of services and identities that have changed.
    - Returns None if smart_mode is False (implying all should be processed).
  returned: always
  type: list
'''

import os
import yaml
import subprocess
from ansible.module_utils.basic import AnsibleModule

def run_git_cmd(module, cmd, cwd):
    """
    Executes a git command and returns the output as a list of lines.
    
    Args:
        module: The AnsibleModule instance.
        cmd: List of command arguments.
        cwd: Current working directory.
        
    Returns:
        list: stdout lines or empty list on failure.
    """
    rc, stdout, stderr = module.run_command(cmd, cwd=cwd)
    if rc != 0:
        return []
    return stdout.splitlines()

def load_yaml_file(path):
    """
    Loads a YAML file safely.
    
    Args:
        path: Absolute path to the file.
        
    Returns:
        dict: Parsed YAML data or empty dict.
    """
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def extract_names(data):
    """
    Extracts names of services and identities from a deployment dict.
    
    Args:
        data: The deployment dictionary.
        
    Returns:
        list: A list of names string.
    """
    names = []
    if not data:
        return names
    
    # Check for root key 'ziti_deployment' or direct structure
    root = data.get('ziti_deployment', data)
    
    if 'services' in root:
        for svc in root['services']:
            if 'name' in svc:
                names.append(svc['name'])
    
    if 'identities' in root:
        for ident in root['identities']:
            if 'name' in ident:
                names.append(ident['name'])
                
    return names

def deep_merge(target, source):
    """
    Merges source dict into target dict recursively (in-place).
    
    Args:
        target: The target dictionary.
        source: The source dictionary to merge in.
        
    Returns:
        dict: The updated target dictionary.
    """
    for k, v in source.items():
        if isinstance(v, dict):
            node = target.setdefault(k, {})
            deep_merge(node, v)
        elif isinstance(v, list):
            target.setdefault(k, []).extend(v)
        else:
            target[k] = v
    return target

def main():
    """
    Main entry point for the OpenZiti Loader module.
    """
    module = AnsibleModule(
        argument_spec=dict(
            base_dir=dict(type='path', required=True),
            smart_mode=dict(type='bool', default=False),
        ),
        supports_check_mode=True
    )

    base_dir = module.params['base_dir']
    smart_mode = module.params['smart_mode']
    
    deployments_dir = os.path.join(base_dir, 'deployments')
    services_dir = os.path.join(deployments_dir, 'services')
    identities_dir = os.path.join(deployments_dir, 'identities')
    
    ziti_deployment = {}
    target_names = set()
    
    # 1. Identify Changed Files (Smart Mode)
    changed_files = set()
    deleted_files = set()
    
    if smart_mode:
        # Check for git repo
        if os.path.exists(os.path.join(base_dir, '.git')):
            # 1. Check for uncommitted changes (LocalOps)
            # git status --porcelain gives us relative paths from root
            lines = run_git_cmd(module, ["git", "status", "--porcelain", "deployments/"], base_dir)
            
            if lines:
                # Parse porcelain output (XY PATH)
                for line in lines:
                    if not line.strip(): continue
                    status = line[:2]
                    path = line[3:].strip()
                    
                    if 'D' in status:
                        deleted_files.add(path)
                    else:
                        changed_files.add(path)
            else:
                # 2. If clean, check the latest commit (CI/CD or Post-Commit Local)
                # We check changes between HEAD~1 and HEAD
                # Output format: STATUS\tPATH
                lines = run_git_cmd(module, ["git", "diff", "--name-status", "HEAD~1", "HEAD", "deployments/"], base_dir)
                
                for line in lines:
                    if not line.strip(): continue
                    parts = line.split(None, 1) # Split by whitespace/tab, max 1 split
                    if len(parts) < 2: continue
                    
                    status = parts[0]
                    path = parts[1].strip()
                    
                    if 'D' in status:
                        deleted_files.add(path)
                    else:
                        changed_files.add(path)

        else:
            module.warn("Smart Mode enabled but .git directory not found. Processing ALL files.")
            smart_mode = False

    # 2. Process ALL files (to build full model) AND extract targets
    # Helper to process a file
    def process_file(filepath, is_deleted=False, content=None):
        file_data = {}
        if is_deleted and content:
            try:
                # Load recovered content from git
                file_data = yaml.safe_load(content) or {}
                # Inject state: absent for all resources found in deleted file
                root = file_data.get('ziti_deployment', file_data)
                if 'services' in root:
                    for svc in root['services']:
                        svc['state'] = 'absent'
                if 'identities' in root:
                    for ident in root['identities']:
                        ident['state'] = 'absent'
            except Exception as e:
                module.warn(f"Failed to parse deleted file content {filepath}: {e}")
                return
        else:
            file_data = load_yaml_file(filepath)

        # Merge into main deployment
        # The structure usually has a root 'ziti_deployment' key, or is the dict itself.
        data_to_merge = file_data.get('ziti_deployment', file_data)
        deep_merge(ziti_deployment, data_to_merge)
        
        # If Smart Mode, check if this file is in our changed list
        rel_path = os.path.relpath(filepath, base_dir)
        
        # Check if this file is relevant for target_names
        if smart_mode:
            if is_deleted or rel_path in changed_files:
                names = extract_names(file_data)
                target_names.update(names)

    # Walk directories
    for root_dir in [services_dir, identities_dir]:
        if not os.path.exists(root_dir):
            continue
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith('.yml') or file.endswith('.yaml'):
                    abs_path = os.path.join(root, file)
                    process_file(abs_path)

    # 3. Process Deleted Files (Smart Mode only)
    if smart_mode:
        for del_path in deleted_files:
            # Recover content from git history
            # git show HEAD:path
            lines = run_git_cmd(module, ["git", "show", f"HEAD:{del_path}"], base_dir)
            content = "\n".join(lines)
            if content:
                # We construct a fake absolute path for logging/logic
                abs_path = os.path.join(base_dir, del_path)
                process_file(abs_path, is_deleted=True, content=content)

    # If NOT smart mode, target_names should be None (indicating process all)
    final_targets = list(target_names) if smart_mode else None

    module.exit_json(
        changed=False,
        ziti_deployment=ziti_deployment,
        target_names=final_targets
    )

if __name__ == '__main__':
    main()
