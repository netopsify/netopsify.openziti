# -*- coding: utf-8 -*-
# Copyright (c) 2024, Mirza Waqas Ahmed <waqas@netopsify.net>
# MIT License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import json
import traceback
from typing import Optional, Dict, Any, List, Union

try:
    import requests
    from pydantic import BaseModel, Field, ValidationError
    HAS_DEPS = True
    IMPORT_ERROR = None
except ImportError as e:
    HAS_DEPS = False
    IMPORT_ERROR = str(e)
    
    # Dummy definitions to prevent NameError during parsing
    class BaseModel:
        def dict(self, **kwargs):
            return {}
            
    def Field(*args, **kwargs):
        return None
        
    class ValidationError(Exception):
        pass

from ansible.module_utils.basic import AnsibleModule


# ==============================================================================
# Pydantic Models
# ==============================================================================

class OpenZitiAuthRequest(BaseModel):
    """Model for authentication request body."""
    username: str
    password: str


class OpenZitiIdentityEnrollment(BaseModel):
    """Model for identity enrollment data."""
    ott: bool = True


class OpenZitiIdentityCreate(BaseModel):
    """Model for creating a new identity."""
    name: str
    type: str = Field(default="Device", description="Type of identity (Device, User, Service)")
    roleAttributes: Optional[List[str]] = None
    enrollment: OpenZitiIdentityEnrollment = Field(default_factory=OpenZitiIdentityEnrollment)
    isAdmin: bool = False


class OpenZitiIdentityType(BaseModel):
    """Model for identity type details."""
    id: str
    name: str


class OpenZitiIdentity(BaseModel):
    """Model for an existing identity."""
    id: str
    name: str
    type: Union[str, OpenZitiIdentityType, Dict[str, Any]]
    isAdmin: bool
    createdAt: Optional[str] = None
    enrollment: Optional[Dict[str, Any]] = None

    def get_type_name(self) -> str:
        if isinstance(self.type, str):
            return self.type
        if isinstance(self.type, OpenZitiIdentityType):
            return self.type.name
        if isinstance(self.type, dict):
            return self.type.get('name', 'Unknown')
        return str(self.type)


class OpenZitiConfigCreate(BaseModel):
    """Model for creating a new config."""
    name: str
    configTypeId: str
    data: Dict[str, Any]


class OpenZitiConfig(BaseModel):
    """Model for an existing config."""
    id: str
    name: str
    configTypeId: str
    data: Dict[str, Any]


class OpenZitiServiceCreate(BaseModel):
    """Model for creating a new service."""
    name: str
    roleAttributes: Optional[List[str]] = None
    configs: Optional[List[str]] = None
    encryptionRequired: bool = True


class OpenZitiService(BaseModel):
    """Model for an existing service."""
    id: str
    name: str
    roleAttributes: Optional[List[str]] = None
    configs: Optional[List[str]] = None
    encryptionRequired: bool


class OpenZitiServicePolicyCreate(BaseModel):
    """Model for creating a new service policy."""
    name: str
    type: str = Field(description="Dial or Bind")
    serviceRoles: List[str]
    identityRoles: List[str]
    semantic: str = Field(default="AnyOf", description="AnyOf or AllOf")


class OpenZitiServicePolicy(BaseModel):
    """Model for an existing service policy."""
    id: str
    name: str
    type: str
    serviceRoles: List[str]
    identityRoles: List[str]
    semantic: str


class OpenZitiRouterPolicyCreate(BaseModel):
    """Model for creating a new edge router policy."""
    name: str
    edgeRouterRoles: List[str]
    identityRoles: List[str]
    semantic: str = Field(default="AnyOf", description="AnyOf or AllOf")


class OpenZitiRouterPolicy(BaseModel):
    """Model for an existing edge router policy."""
    id: str
    name: str
    edgeRouterRoles: List[str]
    identityRoles: List[str]
    semantic: str


class OpenZitiServiceRouterPolicyCreate(BaseModel):
    """Model for creating a new service edge router policy."""
    name: str
    serviceRoles: List[str]
    edgeRouterRoles: List[str]
    semantic: str = Field(default="AnyOf", description="AnyOf or AllOf")


class OpenZitiServiceRouterPolicy(BaseModel):
    """Model for an existing service edge router policy."""
    id: str
    name: str
    serviceRoles: List[str]
    edgeRouterRoles: List[str]
    semantic: str


# ==============================================================================
# API Client
# ==============================================================================

class OpenZitiClient:
    """
    Client for interacting with the OpenZiti Edge Management API.
    """

    def __init__(self, module: AnsibleModule, url: str, verify: bool = True):
        self.module = module
        self.url = url.rstrip('/')
        self.verify = verify
        self.session = requests.Session()
        self.session.verify = verify
        self.token = None

        if not self.verify:
            try:
                from requests.packages.urllib3.exceptions import InsecureRequestWarning
                requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
            except ImportError:
                pass

    def login(self, username, password):
        """
        Authenticates with the OpenZiti controller.
        """
        endpoint = f"{self.url}/edge/management/v1/authenticate?method=password"
        payload = OpenZitiAuthRequest(username=username, password=password)
        
        try:
            response = self.session.post(
                endpoint,
                json=payload.dict(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'token' in data['data']:
                self.token = data['data']['token']
                self.session.headers.update({"zt-session": self.token})
            else:
                self.module.fail_json(msg="Authentication failed: Token not found in response", response=data)
                
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to connect to OpenZiti controller: {str(e)}")
        except ValidationError as e:
            self.module.fail_json(msg=f"Validation error during login: {str(e)}")

    def _get_entity_by_name(self, endpoint_suffix: str, name: str, model_class: Any) -> Any:
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}"
        params = {
            "filter": f'name="{name}"'
        }
        
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and len(data['data']) > 0:
                return model_class(**data['data'][0])
            return None
            
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to retrieve {endpoint_suffix}: {str(e)}")
        except ValidationError as e:
            self.module.fail_json(msg=f"Data validation error for {endpoint_suffix}: {str(e)}")
        return None

    def _create_entity(self, endpoint_suffix: str, entity_data: BaseModel, model_class: Any) -> Any:
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}"
        
        try:
            response = self.session.post(
                endpoint,
                json=entity_data.dict(exclude_none=True),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'id' in data['data']:
                return self._get_entity_by_id(endpoint_suffix, data['data']['id'], model_class)
            else:
                self.module.fail_json(msg=f"Failed to create {endpoint_suffix}: ID not returned", response=data)
                
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to create {endpoint_suffix}: {str(e)}", response=getattr(e.response, 'text', ''))
        return None

    def _get_entity_by_id(self, endpoint_suffix: str, entity_id: str, model_class: Any) -> Any:
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}/{entity_id}"
        
        try:
            response = self.session.get(endpoint)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                return model_class(**data['data'])
            return None
            
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to retrieve {endpoint_suffix} by ID: {str(e)}")
        return None

    def _delete_entity(self, endpoint_suffix: str, entity_id: str):
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}/{entity_id}"
        
        try:
            response = self.session.delete(endpoint)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to delete {endpoint_suffix}: {str(e)}")

    def _update_entity(self, endpoint_suffix: str, entity_id: str, entity_data: BaseModel) -> Any:
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}/{entity_id}"
        
        try:
            response = self.session.put(
                endpoint,
                json=entity_data.dict(exclude_none=True),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            # PUT usually returns empty body or just success status, we might want to re-fetch
            # But for now let's assume success if no error
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to update {endpoint_suffix}: {str(e)}")

    # Identity Methods
    def get_identity_by_name(self, name: str) -> Optional[OpenZitiIdentity]:
        return self._get_entity_by_name("identities", name, OpenZitiIdentity)

    def create_identity(self, identity_data: OpenZitiIdentityCreate) -> OpenZitiIdentity:
        return self._create_entity("identities", identity_data, OpenZitiIdentity)

    def get_identity_by_id(self, identity_id: str) -> Optional[OpenZitiIdentity]:
        return self._get_entity_by_id("identities", identity_id, OpenZitiIdentity)

    def delete_identity(self, identity_id: str):
        self._delete_entity("identities", identity_id)

    def get_enrollment_jwt(self, identity_id: str) -> Optional[str]:
        identity = self.get_identity_by_id(identity_id)
        if identity and identity.enrollment and 'ott' in identity.enrollment:
            return identity.enrollment['ott'].get('jwt')
        return None

    # Config Methods
    def get_config_by_name(self, name: str) -> Optional[OpenZitiConfig]:
        return self._get_entity_by_name("configs", name, OpenZitiConfig)

    def create_config(self, config_data: OpenZitiConfigCreate) -> OpenZitiConfig:
        return self._create_entity("configs", config_data, OpenZitiConfig)
    
    def delete_config(self, config_id: str):
        self._delete_entity("configs", config_id)

    def get_config_type_by_name(self, name: str) -> Optional[str]:
        # Helper to get config type ID by name
        endpoint = f"{self.url}/edge/management/v1/config-types"
        params = {"filter": f'name="{name}"'}
        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                return data['data'][0]['id']
        except Exception:
            pass
        return None

    # Service Methods
    def get_service_by_name(self, name: str) -> Optional[OpenZitiService]:
        return self._get_entity_by_name("services", name, OpenZitiService)

    def create_service(self, service_data: OpenZitiServiceCreate) -> OpenZitiService:
        return self._create_entity("services", service_data, OpenZitiService)

    def delete_service(self, service_id: str):
        self._delete_entity("services", service_id)

    # Service Policy Methods
    def get_service_policy_by_name(self, name: str) -> Optional[OpenZitiServicePolicy]:
        return self._get_entity_by_name("service-policies", name, OpenZitiServicePolicy)

    def create_service_policy(self, policy_data: OpenZitiServicePolicyCreate) -> OpenZitiServicePolicy:
        return self._create_entity("service-policies", policy_data, OpenZitiServicePolicy)

    def delete_service_policy(self, policy_id: str):
        self._delete_entity("service-policies", policy_id)

    # Router Policy Methods
    def get_router_policy_by_name(self, name: str) -> Optional[OpenZitiRouterPolicy]:
        return self._get_entity_by_name("edge-router-policies", name, OpenZitiRouterPolicy)

    def create_router_policy(self, policy_data: OpenZitiRouterPolicyCreate) -> OpenZitiRouterPolicy:
        return self._create_entity("edge-router-policies", policy_data, OpenZitiRouterPolicy)

    def delete_router_policy(self, policy_id: str):
        self._delete_entity("edge-router-policies", policy_id)

    # Service Router Policy Methods
    def get_service_router_policy_by_name(self, name: str) -> Optional[OpenZitiServiceRouterPolicy]:
        return self._get_entity_by_name("service-edge-router-policies", name, OpenZitiServiceRouterPolicy)

    def create_service_router_policy(self, policy_data: OpenZitiServiceRouterPolicyCreate) -> OpenZitiServiceRouterPolicy:
        return self._create_entity("service-edge-router-policies", policy_data, OpenZitiServiceRouterPolicy)

    def delete_service_router_policy(self, policy_id: str):
        self._delete_entity("service-edge-router-policies", policy_id)
