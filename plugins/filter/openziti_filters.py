#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

class FilterModule(object):
    """
    Ansible Filter Plugin for converting OpenZiti deployment definitions into flat lists
    consumable by the OpenZiti Ansible Collection modules.
    
    This filter is the core transformation engine that enables the "One file per service"
    abstraction pattern.
    """
    
    def filters(self):
        """
        Returns the list of filter functions provided by this module.
        """
        return {
            'ziti_transform': self.ziti_transform
        }

    def ziti_transform(self, deployment_data, target_names=None):
        """
        Transforms high-level OpenZiti deployment data into specific Ansible module parameters.

        This function takes a hierarchical deployment definition (containing services, identities,
        roles, policies, etc.) and flattens it into separate lists for:
          - Identities
          - Configs (Host, Intercept)
          - Services
          - Service Policies (Dial, Bind)
          - Edge Router Policies
          - Service Edge Router Policies

        Args:
            deployment_data (dict): The dictionary containing the merged deployment definitions.
                                    This is typically the output of the 'openziti_loader' module.
            target_names (list, optional): A list of specific service or identity names to process.
                                           Used by **Smart Mode** to filter the output to only
                                           changed resources. If None or empty, all resources
                                           in `deployment_data` are processed.

        Returns:
            dict: A dictionary containing lists of resources:
                - openziti_identities
                - openziti_configs
                - openziti_services
                - openziti_service_policies
                - openziti_router_policies
                - openziti_service_router_policies

        Example Data Structure (Input):
            deployment_data = {
                'services': [{
                    'name': 'web-service',
                    'host': { ... },
                    'intercept': { ... },
                    'policies': { 'dial': ..., 'bind': ... }
                }]
            }

        Example Output:
            {
                'openziti_services': [{ 'name': 'web-service', ... }],
                'openziti_configs': [{ 'name': 'web-service-host-v1', ... }, ...],
                'openziti_service_policies': [{ 'name': 'web-service-dial', ... }, ...]
            }
        """
        if not deployment_data:
            return {
                'openziti_identities': [],
                'openziti_configs': [],
                'openziti_services': [],
                'openziti_service_policies': [],
                'openziti_router_policies': [],
                'openziti_service_router_policies': []
            }

        # Initialize output lists
        identities = []
        configs = []
        services = []
        service_policies = []
        router_policies = []
        service_router_policies = []

        # Parse Defaults
        defaults = deployment_data.get('defaults') or {}
        default_router_roles = defaults.get('router_roles') or ['#all']
        default_encryption = defaults.get('encryption', True)
        default_create_router_policies = defaults.get('create_router_policies', False)

        # Helper to check if we should process a resource (Smart Mode Logic)
        def should_process(name):
            if not target_names:
                return True
            return name in target_names
        
        # 1. Process Identities
        all_identities = deployment_data.get('identities') or []
        
        for ident in all_identities:
            if not ident: continue
            
            # Smart Mode: Skip if identity name is not in target list
            if not should_process(ident['name']):
                continue
                
            raw_role_attributes = ident.get('role_attributes') or []
            role_attributes = [r.lstrip('#') for r in raw_role_attributes]

            # Merge 'tags' into role_attributes as a convenience
            if ident.get('tags'):
                for tag in ident['tags']:
                    role_attributes.append(tag)
            
            identities.append({
                'name': ident['name'],
                'type': ident.get('type', 'Device'),
                'role_attributes': role_attributes,
                'enrollment_method': ident.get('enrollment_method', 'ott'),
                'state': ident.get('state', 'present')
            })

        # 2. Process Services
        for svc in (deployment_data.get('services') or []):
            if not svc: continue
            svc_name = svc['name']
            
            # Smart Mode: Skip if service name is not in target list
            if not should_process(svc_name):
                continue
            
            # If state is absent, we still need to process identifying info to delete it
            svc_state = svc.get('state', 'present')
            svc_role_attr = svc_name # Auto-generated role attribute for the service matches its name
            
            # --- Configs Processing ---
            svc_config_names = []
            
            # A. Host Config
            if svc.get('host'):
                host_cfg_name = f"{svc_name}-host-v1"
                host_data = svc['host']
                if 'protocol' not in host_data:
                    host_data['protocol'] = 'tcp'
                
                configs.append({
                    'name': host_cfg_name,
                    'type': 'host.v1',
                    'data': host_data,
                    'state': svc_state
                })
                svc_config_names.append(host_cfg_name)

            # B. Intercept Config
            if svc.get('intercept'):
                int_cfg_name = f"{svc_name}-intercept-v1"
                int_data = svc['intercept']
                
                # Normalize 'port' -> 'portRanges'
                if 'port' in int_data:
                    int_data['portRanges'] = [{'low': int_data['port'], 'high': int_data['port']}]
                    del int_data['port']
                elif 'port_ranges' in int_data:
                    int_data['portRanges'] = int_data['port_ranges']
                    del int_data['port_ranges']
                
                # Normalize 'protocol' -> 'protocols'
                if 'protocol' in int_data:
                    int_data['protocols'] = [int_data['protocol']]
                    del int_data['protocol']
                elif 'protocols' not in int_data:
                    int_data['protocols'] = ['tcp']

                # Normalize 'address' -> 'addresses'
                if 'address' in int_data:
                    int_data['addresses'] = [int_data['address']]
                    del int_data['address']

                configs.append({
                    'name': int_cfg_name,
                    'type': 'intercept.v1',
                    'data': int_data,
                    'state': svc_state
                })
                svc_config_names.append(int_cfg_name)

            # --- Service Definition ---
            raw_svc_role_attrs = svc.get('role_attributes') or svc.get('roles') or [svc_role_attr]
            svc_role_attrs = [r.lstrip('#') for r in raw_svc_role_attrs]

            services.append({
                'name': svc_name,
                'role_attributes': svc_role_attrs,
                'configs': svc_config_names,
                'encryption_required': svc.get('encryption', default_encryption),
                'state': svc_state
            })

            # --- Policies Processing ---
            policies = svc.get('policies') or {}
            
            # C. Bind Policy
            if policies.get('bind'):
                bind_pol = policies['bind']
                raw_id_roles = bind_pol.get('roles') or []
                id_roles = []
                for r in raw_id_roles:
                    if r.startswith('@') or r.startswith('#'):
                        id_roles.append(r)
                    else:
                        id_roles.append(f"#{r}")
                if 'identity' in bind_pol:
                    id_roles.append(f"#{bind_pol['identity']}")
                
                raw_extra_svc_roles = bind_pol.get('service_roles') or []
                extra_svc_roles = []
                for r in raw_extra_svc_roles:
                    if r.startswith('@') or r.startswith('#'):
                        extra_svc_roles.append(r)
                    else:
                        extra_svc_roles.append(f"#{r}")
                final_svc_roles = [f"#{svc_name}"] + extra_svc_roles
                
                service_policies.append({
                    'name': f"{svc_name}-bind",
                    'type': 'Bind',
                    'service_roles': final_svc_roles,
                    'identity_roles': id_roles,
                    'semantic': bind_pol.get('semantic', 'AnyOf'),
                    'state': svc_state
                })

            # D. Dial Policy
            if policies.get('dial'):
                dial_pol = policies['dial']
                raw_id_roles = dial_pol.get('roles') or []
                id_roles = []
                for r in raw_id_roles:
                    if r.startswith('@') or r.startswith('#'):
                        id_roles.append(r)
                    else:
                        id_roles.append(f"#{r}")
                if 'identity' in dial_pol:
                    id_roles.append(f"#{dial_pol['identity']}")

                raw_extra_svc_roles = dial_pol.get('service_roles') or []
                extra_svc_roles = []
                for r in raw_extra_svc_roles:
                    if r.startswith('@') or r.startswith('#'):
                        extra_svc_roles.append(r)
                    else:
                        extra_svc_roles.append(f"#{r}")
                final_svc_roles = [f"#{svc_name}"] + extra_svc_roles

                service_policies.append({
                    'name': f"{svc_name}-dial",
                    'type': 'Dial',
                    'service_roles': final_svc_roles,
                    'identity_roles': id_roles,
                    'semantic': dial_pol.get('semantic', 'AnyOf'),
                    'state': svc_state
                })

            # E. Service Edge Router Policy
            router_pol_def = policies.get('router')
            create_router_pol = False
            
            if router_pol_def is False:
                create_router_pol = False
            elif router_pol_def is not None:
                create_router_pol = True
            elif default_create_router_policies:
                create_router_pol = True
                router_pol_def = {} # Defaults

            if create_router_pol:
                er_roles = router_pol_def.get('roles') or default_router_roles
                service_router_policies.append({
                    'name': f"{svc_name}-router",
                    'service_roles': [f"#{svc_name}"],
                    'edge_router_roles': er_roles,
                    'semantic': router_pol_def.get('semantic', 'AnyOf'),
                    'state': svc_state
                })

        # 3. Process Edge Router Policies (Global)
        for rp in (deployment_data.get('router_policies') or []):
            if not rp: continue
            router_policies.append({
                'name': rp['name'],
                'edge_router_roles': rp.get('edge_router_roles') or ['#all'],
                'identity_roles': rp.get('identity_roles') or ['#all'],
                'semantic': rp.get('semantic', 'AnyOf'),
                'state': rp.get('state', 'present')
            })

        return {
            'openziti_identities': identities,
            'openziti_configs': configs,
            'openziti_services': services,
            'openziti_service_policies': service_policies,
            'openziti_router_policies': router_policies,
            'openziti_service_router_policies': service_router_policies
        }
