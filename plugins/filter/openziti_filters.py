#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

class FilterModule(object):
    def filters(self):
        return {
            'ziti_transform': self.ziti_transform
        }

    def ziti_transform(self, deployment_data, target_services=None):
        """
        Transforms the high-level OpenZiti deployment data model into flat lists
        required by the Ansible modules.
        
        Args:
            deployment_data (dict): The full ziti_deployment dictionary.
            target_services (list, optional): List of service names to filter by. 
                                              If None or empty, processes all.
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
        defaults = deployment_data.get('defaults', {})
        default_router_roles = defaults.get('router_roles', ['#all'])
        default_encryption = defaults.get('encryption', True)
        default_create_router_policies = defaults.get('create_router_policies', False)

        # Helper to check if we should process a service
        def should_process(name):
            if not target_services:
                return True
            return name in target_services
        
        all_identities = deployment_data.get('identities', [])
        
        for ident in all_identities:
            raw_role_attributes = ident.get('role_attributes', [])
            role_attributes = [r.lstrip('#') for r in raw_role_attributes]

            if 'tags' in ident:
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
        for svc in deployment_data.get('services', []):
            svc_name = svc['name']
            
            if not should_process(svc_name):
                continue

            svc_state = svc.get('state', 'present')
            svc_role_attr = svc_name # Auto-role for the service
            
            # Configs
            svc_config_names = []
            
            # Host Config
            if 'host' in svc:
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

            # Intercept Config
            if 'intercept' in svc:
                int_cfg_name = f"{svc_name}-intercept-v1"
                int_data = svc['intercept']
                
                # Normalize Port Ranges
                if 'port' in int_data:
                    int_data['portRanges'] = [{'low': int_data['port'], 'high': int_data['port']}]
                    del int_data['port']
                elif 'port_ranges' in int_data:
                    int_data['portRanges'] = int_data['port_ranges']
                    del int_data['port_ranges']
                
                # Normalize Protocols
                if 'protocol' in int_data:
                    int_data['protocols'] = [int_data['protocol']]
                    del int_data['protocol']
                elif 'protocols' not in int_data:
                    int_data['protocols'] = ['tcp']

                # Normalize Addresses
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

            # Service Definition
            raw_svc_role_attrs = svc.get('role_attributes', [svc_role_attr])
            svc_role_attrs = [r.lstrip('#') for r in raw_svc_role_attrs]

            services.append({
                'name': svc_name,
                'role_attributes': svc_role_attrs,
                'configs': svc_config_names,
                'encryption_required': svc.get('encryption', default_encryption),
                'state': svc_state
            })

            # Policies
            policies = svc.get('policies', {})
            
            # Bind Policy
            if 'bind' in policies:
                bind_pol = policies['bind']
                id_roles = bind_pol.get('roles', [])
                if 'identity' in bind_pol:
                    # If referencing an identity by name, we assume it has a role attribute #identity_name
                    # This is a convention.
                    id_roles.append(f"#{bind_pol['identity']}")
                
                service_policies.append({
                    'name': f"{svc_name}-bind",
                    'type': 'Bind',
                    'service_roles': [f"#{svc_name}"],
                    'identity_roles': id_roles,
                    'semantic': bind_pol.get('semantic', 'AnyOf'),
                    'state': svc_state
                })

            # Dial Policy
            if 'dial' in policies:
                dial_pol = policies['dial']
                id_roles = dial_pol.get('roles', [])
                if 'identity' in dial_pol:
                    id_roles.append(f"#{dial_pol['identity']}")

                service_policies.append({
                    'name': f"{svc_name}-dial",
                    'type': 'Dial',
                    'service_roles': [f"#{svc_name}"],
                    'identity_roles': id_roles,
                    'semantic': dial_pol.get('semantic', 'AnyOf'),
                    'state': svc_state
                })

            # Router Policy (Service Edge Router Policy)
            router_pol_def = policies.get('router')
            create_router_pol = False
            
            if router_pol_def is False:
                create_router_pol = False
            elif router_pol_def is not None:
                create_router_pol = True
            elif default_create_router_policies:
                create_router_pol = True
                router_pol_def = {} # Use defaults

            if create_router_pol:
                er_roles = router_pol_def.get('roles', default_router_roles)
                service_router_policies.append({
                    'name': f"{svc_name}-router",
                    'service_roles': [f"#{svc_name}"],
                    'edge_router_roles': er_roles,
                    'semantic': router_pol_def.get('semantic', 'AnyOf'),
                    'state': svc_state
                })

        # 3. Process Edge Router Policies (Global)
        for rp in deployment_data.get('router_policies', []):
            router_policies.append({
                'name': rp['name'],
                'edge_router_roles': rp.get('edge_router_roles', ['#all']),
                'identity_roles': rp.get('identity_roles', ['#all']),
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
