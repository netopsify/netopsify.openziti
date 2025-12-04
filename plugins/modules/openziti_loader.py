#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: openziti_loader
short_description: Loads OpenZiti deployment definitions with Smart Mode support
description:
  - Scans the deployments directory for YAML definitions.
  - Merges them into a single data structure.
  - Implements Smart Mode: detects changed/deleted files via Git, recovers deleted content, and identifies target resources.
options:
  base_dir:
    description: Base directory containing the 'deployments' folder.
    required: true
    type: path
  smart_mode:
    description: Enable Smart Mode to only target changed resources.
    type: bool
    default: false
author:
  - Netopsify
'''

EXAMPLES = r'''
- name: Load OpenZiti Definitions
  netopsify.openziti.openziti_loader:
    base_dir: "{{ playbook_dir }}"
    smart_mode: true
  register: ziti_data
'''

RETURN = r'''
ziti_deployment:
  description: The merged deployment data structure.
  type: dict
target_names:
  description: List of service/identity names that were changed (if smart_mode is True).
  type: list
'''

import os
import yaml
import subprocess
from ansible.module_utils.basic import AnsibleModule

def run_git_cmd(module, cmd, cwd):
    rc, stdout, stderr = module.run_command(cmd, cwd=cwd)
    if rc != 0:
        # If git fails (e.g. not a repo), we might want to warn and fallback to full mode?
        # For now, let's log it.
        return []
    return stdout.splitlines()

def load_yaml_file(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def extract_names(data):
    """Extracts names of services and identities from a deployment dict."""
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
    """Merges source dict into target dict recursively."""
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
            # Get changed files (modified, added)
            # We look at both staged and unstaged changes
            # git status --porcelain gives us relative paths from root
            lines = run_git_cmd(module, ["git", "status", "--porcelain", "deployments/"], base_dir)
            for line in lines:
                if not line.strip(): continue
                status = line[:2]
                path = line[3:].strip()
                
                if 'D' in status:
                    deleted_files.add(path)
                else:
                    changed_files.add(path)
        else:
            module.warn("Smart Mode enabled but .git directory not found. Processing ALL files.")
            smart_mode = False

    # 2. Process ALL files (to build full model) AND extract targets
    # We walk the directories.
    
    # Helper to process a file
    def process_file(filepath, is_deleted=False, content=None):
        file_data = {}
        if is_deleted and content:
            try:
                file_data = yaml.safe_load(content) or {}
                # Inject state: absent
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
        # We want to merge the INNER content if 'ziti_deployment' key exists.
        data_to_merge = file_data.get('ziti_deployment', file_data)
        deep_merge(ziti_deployment, data_to_merge)
        
        # If Smart Mode, check if this file is in our changed list
        # We need to match paths.
        # filepath is absolute. changed_files are relative to base_dir.
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
            # Recover content
            # git show HEAD:path
            # Note: git show expects path relative to repo root. 
            # If base_dir is repo root, del_path is correct.
            lines = run_git_cmd(module, ["git", "show", f"HEAD:{del_path}"], base_dir)
            content = "\n".join(lines)
            if content:
                # We process this "ghost" file
                # We construct a fake absolute path for logging/logic
                abs_path = os.path.join(base_dir, del_path)
                process_file(abs_path, is_deleted=True, content=content)

    # If NOT smart mode, target_names should be None (process all)
    final_targets = list(target_names) if smart_mode else None

    module.exit_json(
        changed=False,
        ziti_deployment=ziti_deployment,
        target_names=final_targets
    )

if __name__ == '__main__':
    main()
