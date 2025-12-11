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
    """
    Model for authentication request body.

    Attributes:
        username (str): The username for authentication.
        password (str): The password for authentication.
    """
    username: str
    password: str


class OpenZitiIdentityEnrollment(BaseModel):
    """
    Model for identity enrollment data.

    Attributes:
        ott (bool): Whether to use One-Time Token enrollment. Defaults to True.
    """
    ott: bool = True


class OpenZitiIdentityCreate(BaseModel):
    """
    Model for creating a new identity.

    Attributes:
        name (str): The name of the identity.
        type (str): Type of identity (Device, User, Service). Defaults to "Device".
        roleAttributes (Optional[List[str]]): List of role attributes.
        enrollment (OpenZitiIdentityEnrollment): Enrollment settings.
        isAdmin (bool): Whether the identity is an admin. Defaults to False.
    """
    name: str
    type: str = Field(default="Device", description="Type of identity (Device, User, Service)")
    roleAttributes: Optional[List[str]] = None
    enrollment: OpenZitiIdentityEnrollment = Field(default_factory=OpenZitiIdentityEnrollment)
    isAdmin: bool = False


class OpenZitiIdentityType(BaseModel):
    """
    Model for identity type details.

    Attributes:
        id (str): The unique identifier of the identity type.
        name (str): The name of the identity type.
    """
    id: str
    name: str


class OpenZitiIdentity(BaseModel):
    """
    Model for an existing identity.

    Attributes:
        id (str): The unique identifier of the identity.
        name (str): The name of the identity.
        type (Union[str, OpenZitiIdentityType, Dict[str, Any]]): The type of the identity.
        isAdmin (bool): Whether the identity is an admin.
        roleAttributes (Optional[List[str]]): List of role attributes.
        createdAt (Optional[str]): Creation timestamp.
        enrollment (Optional[Dict[str, Any]]): Enrollment details.
    """
    id: str
    name: str
    type: Union[str, OpenZitiIdentityType, Dict[str, Any]]
    isAdmin: bool
    roleAttributes: Optional[List[str]] = None
    createdAt: Optional[str] = None
    enrollment: Optional[Dict[str, Any]] = None

    def get_type_name(self) -> str:
        """
        Retrieves the string representation of the identity type name.

        Returns:
            str: The name of the identity type.
        """
        if isinstance(self.type, str):
            return self.type
        if isinstance(self.type, OpenZitiIdentityType):
            return self.type.name
        if isinstance(self.type, dict):
            return self.type.get('name', 'Unknown')
        return str(self.type)


class OpenZitiConfigCreate(BaseModel):
    """
    Model for creating a new config.

    Attributes:
        name (str): The name of the configuration.
        configTypeId (str): The ID of the configuration type.
        data (Dict[str, Any]): The configuration data payload.
    """
    name: str
    configTypeId: str
    data: Dict[str, Any]


class OpenZitiConfig(BaseModel):
    """
    Model for an existing config.

    Attributes:
        id (str): The unique identifier of the config.
        name (str): The name of the config.
        configTypeId (str): The ID of the config type.
        data (Dict[str, Any]): The configuration data payload.
    """
    id: str
    name: str
    configTypeId: str
    data: Dict[str, Any]


class OpenZitiServiceCreate(BaseModel):
    """
    Model for creating a new service.

    Attributes:
        name (str): The name of the service.
        roleAttributes (Optional[List[str]]): List of role attributes.
        configs (Optional[List[str]]): List of configuration IDs.
        encryptionRequired (bool): Whether encryption is required. Defaults to True.
    """
    name: str
    roleAttributes: Optional[List[str]] = None
    configs: Optional[List[str]] = None
    encryptionRequired: bool = True


class OpenZitiService(BaseModel):
    """
    Model for an existing service.

    Attributes:
        id (str): The unique identifier of the service.
        name (str): The name of the service.
        roleAttributes (Optional[List[str]]): List of role attributes.
        configs (Optional[List[str]]): List of configuration IDs.
        encryptionRequired (bool): Whether encryption is required.
    """
    id: str
    name: str
    roleAttributes: Optional[List[str]] = None
    configs: Optional[List[str]] = None
    encryptionRequired: bool


class OpenZitiServicePolicyCreate(BaseModel):
    """
    Model for creating a new service policy.

    Attributes:
        name (str): The name of the policy.
        type (str): The type of policy ("Dial" or "Bind").
        serviceRoles (List[str]): List of service roles.
        identityRoles (List[str]): List of identity roles.
        semantic (str): The semantic logic ("AnyOf" or "AllOf"). Defaults to "AnyOf".
    """
    name: str
    type: str = Field(description="Dial or Bind")
    serviceRoles: List[str]
    identityRoles: List[str]
    semantic: str = Field(default="AnyOf", description="AnyOf or AllOf")


class OpenZitiServicePolicy(BaseModel):
    """
    Model for an existing service policy.

    Attributes:
        id (str): The unique identifier of the policy.
        name (str): The name of the policy.
        type (str): The type of policy.
        serviceRoles (List[str]): List of service roles.
        identityRoles (List[str]): List of identity roles.
        semantic (str): The semantic logic.
    """
    id: str
    name: str
    type: str
    serviceRoles: List[str]
    identityRoles: List[str]
    semantic: str


class OpenZitiRouterPolicyCreate(BaseModel):
    """
    Model for creating a new edge router policy.

    Attributes:
        name (str): The name of the policy.
        edgeRouterRoles (List[str]): List of edge router roles.
        identityRoles (List[str]): List of identity roles.
        semantic (str): The semantic logic ("AnyOf" or "AllOf"). Defaults to "AnyOf".
    """
    name: str
    edgeRouterRoles: List[str]
    identityRoles: List[str]
    semantic: str = Field(default="AnyOf", description="AnyOf or AllOf")


class OpenZitiRouterPolicy(BaseModel):
    """
    Model for an existing edge router policy.

    Attributes:
        id (str): The unique identifier of the policy.
        name (str): The name of the policy.
        edgeRouterRoles (List[str]): List of edge router roles.
        identityRoles (List[str]): List of identity roles.
        semantic (str): The semantic logic.
    """
    id: str
    name: str
    edgeRouterRoles: List[str]
    identityRoles: List[str]
    semantic: str


class OpenZitiServiceRouterPolicyCreate(BaseModel):
    """
    Model for creating a new service edge router policy.

    Attributes:
        name (str): The name of the policy.
        serviceRoles (List[str]): List of service roles.
        edgeRouterRoles (List[str]): List of edge router roles.
        semantic (str): The semantic logic ("AnyOf" or "AllOf"). Defaults to "AnyOf".
    """
    name: str
    serviceRoles: List[str]
    edgeRouterRoles: List[str]
    semantic: str = Field(default="AnyOf", description="AnyOf or AllOf")


class OpenZitiServiceRouterPolicy(BaseModel):
    """
    Model for an existing service edge router policy.

    Attributes:
        id (str): The unique identifier of the policy.
        name (str): The name of the policy.
        serviceRoles (List[str]): List of service roles.
        edgeRouterRoles (List[str]): List of edge router roles.
        semantic (str): The semantic logic.
    """
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
    
    This class handles authentication and creates a simplified interface for 
    creating, retrieving, updating, and deleting OpenZiti entities.
    """

    def __init__(self, module: AnsibleModule, url: str, verify: bool = True):
        """
        Initialize the OpenZiti Client.

        Args:
            module (AnsibleModule): The Ansible module instance for error reporting.
            url (str): The base URL of the OpenZiti Controller.
            verify (bool, optional): Whether to verify SSL certificates. Defaults to True.
        """
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
        Authenticates with the OpenZiti controller using username and password.
        
        Upon success, the session token is stored and added to subsequent request headers.
        
        Args:
            username (str): The username.
            password (str): The password.
            
        Raises:
            Fails the Ansible module if authentication fails.
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
        """
        Generic internal method to retrieve a single entity by its name.
        
        Args:
            endpoint_suffix (str): The API endpoint suffix (e.g., 'identities').
            name (str): The name of the entity to search for.
            model_class (Any): The Pydantic model class to parse the result into.
            
        Returns:
            Any: An instance of model_class if found, otherwise None.
        """
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
        """
        Generic internal method to create a new entity.
        
        Args:
            endpoint_suffix (str): The API endpoint suffix.
            entity_data (BaseModel): The data model containing the creation payload.
            model_class (Any): The Pydantic model class to return.
            
        Returns:
            Any: An instance of the created entity model.
        """
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
        """
        Generic internal method to retrieve an entity by its ID.
        """
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
        """
        Generic internal method to delete an entity by its ID.
        """
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}/{entity_id}"
        
        try:
            response = self.session.delete(endpoint)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to delete {endpoint_suffix}: {str(e)}")

    def _update_entity(self, endpoint_suffix: str, entity_id: str, entity_data: BaseModel) -> Any:
        """
        Generic internal method to update an existing entity.
        
        Args:
            endpoint_suffix (str): The API endpoint suffix.
            entity_id (str): The ID of the entity to update.
            entity_data (BaseModel): The payload with updated data.
        """
        endpoint = f"{self.url}/edge/management/v1/{endpoint_suffix}/{entity_id}"
        
        try:
            response = self.session.put(
                endpoint,
                json=entity_data.dict(exclude_none=True),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.module.fail_json(msg=f"Failed to update {endpoint_suffix}: {str(e)}")

    # -------------------------------------------------------------------------
    # Identity Methods
    # -------------------------------------------------------------------------

    def get_identity_by_name(self, name: str) -> Optional[OpenZitiIdentity]:
        """Retrieves an identity by name."""
        return self._get_entity_by_name("identities", name, OpenZitiIdentity)

    def create_identity(self, identity_data: OpenZitiIdentityCreate) -> OpenZitiIdentity:
        """Creates a new identity."""
        return self._create_entity("identities", identity_data, OpenZitiIdentity)

    def get_identity_by_id(self, identity_id: str) -> Optional[OpenZitiIdentity]:
        """Retrieves an identity by ID."""
        return self._get_entity_by_id("identities", identity_id, OpenZitiIdentity)

    def update_identity(self, identity_id: str, identity_data: OpenZitiIdentityCreate):
        """Updates an existing identity."""
        self._update_entity("identities", identity_id, identity_data)

    def delete_identity(self, identity_id: str):
        """Deletes an identity."""
        self._delete_entity("identities", identity_id)

    def get_enrollment_jwt(self, identity_id: str) -> Optional[str]:
        """
        Retrieves the enrollment JWT for an identity if available.
        
        Args:
            identity_id (str): The ID of the identity.
            
        Returns:
            Optional[str]: The JWT string if found, else None.
        """
        identity = self.get_identity_by_id(identity_id)
        if identity and identity.enrollment and 'ott' in identity.enrollment:
            return identity.enrollment['ott'].get('jwt')
        return None

    # -------------------------------------------------------------------------
    # Config Methods
    # -------------------------------------------------------------------------

    def get_config_by_name(self, name: str) -> Optional[OpenZitiConfig]:
        """Retrieves a configuration by name."""
        return self._get_entity_by_name("configs", name, OpenZitiConfig)

    def create_config(self, config_data: OpenZitiConfigCreate) -> OpenZitiConfig:
        """Creates a new configuration."""
        return self._create_entity("configs", config_data, OpenZitiConfig)
    
    def update_config(self, config_id: str, config_data: OpenZitiConfigCreate):
        """Updates an existing configuration."""
        self._update_entity("configs", config_id, config_data)

    def delete_config(self, config_id: str):
        """Deletes a configuration."""
        self._delete_entity("configs", config_id)

    def get_config_type_by_name(self, name: str) -> Optional[str]:
        """
        Helper to resolve a Config Type Name to its ID.
        
        Args:
            name (str): The name of the config type (e.g., 'host.v1').
            
        Returns:
            Optional[str]: The ID of the config type if found.
        """
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

    # -------------------------------------------------------------------------
    # Service Methods
    # -------------------------------------------------------------------------

    def get_service_by_name(self, name: str) -> Optional[OpenZitiService]:
        """Retrieves a service by name."""
        return self._get_entity_by_name("services", name, OpenZitiService)

    def create_service(self, service_data: OpenZitiServiceCreate) -> OpenZitiService:
        """Creates a new service."""
        return self._create_entity("services", service_data, OpenZitiService)

    def update_service(self, service_id: str, service_data: OpenZitiServiceCreate):
        """Updates an existing service."""
        self._update_entity("services", service_id, service_data)

    def delete_service(self, service_id: str):
        """Deletes a service."""
        self._delete_entity("services", service_id)

    # -------------------------------------------------------------------------
    # Service Policy Methods
    # -------------------------------------------------------------------------

    def get_service_policy_by_name(self, name: str) -> Optional[OpenZitiServicePolicy]:
        """Retrieves a service policy by name."""
        return self._get_entity_by_name("service-policies", name, OpenZitiServicePolicy)

    def create_service_policy(self, policy_data: OpenZitiServicePolicyCreate) -> OpenZitiServicePolicy:
        """Creates a new service policy."""
        return self._create_entity("service-policies", policy_data, OpenZitiServicePolicy)

    def update_service_policy(self, policy_id: str, policy_data: OpenZitiServicePolicyCreate):
        """Updates an existing service policy."""
        self._update_entity("service-policies", policy_id, policy_data)

    def delete_service_policy(self, policy_id: str):
        """Deletes a service policy."""
        self._delete_entity("service-policies", policy_id)

    # -------------------------------------------------------------------------
    # Router Policy Methods
    # -------------------------------------------------------------------------

    def get_router_policy_by_name(self, name: str) -> Optional[OpenZitiRouterPolicy]:
        """Retrieves a router policy by name."""
        return self._get_entity_by_name("edge-router-policies", name, OpenZitiRouterPolicy)

    def create_router_policy(self, policy_data: OpenZitiRouterPolicyCreate) -> OpenZitiRouterPolicy:
        """Creates a new router policy."""
        return self._create_entity("edge-router-policies", policy_data, OpenZitiRouterPolicy)

    def update_router_policy(self, policy_id: str, policy_data: OpenZitiRouterPolicyCreate):
        """Updates an existing router policy."""
        self._update_entity("edge-router-policies", policy_id, policy_data)

    def delete_router_policy(self, policy_id: str):
        """Deletes a router policy."""
        self._delete_entity("edge-router-policies", policy_id)

    # -------------------------------------------------------------------------
    # Service Router Policy Methods
    # -------------------------------------------------------------------------

    def get_service_router_policy_by_name(self, name: str) -> Optional[OpenZitiServiceRouterPolicy]:
        """Retrieves a service router policy by name."""
        return self._get_entity_by_name("service-edge-router-policies", name, OpenZitiServiceRouterPolicy)

    def create_service_router_policy(self, policy_data: OpenZitiServiceRouterPolicyCreate) -> OpenZitiServiceRouterPolicy:
        """Creates a new service router policy."""
        return self._create_entity("service-edge-router-policies", policy_data, OpenZitiServiceRouterPolicy)

    def update_service_router_policy(self, policy_id: str, policy_data: OpenZitiServiceRouterPolicyCreate):
        """Updates an existing service router policy."""
        self._update_entity("service-edge-router-policies", policy_id, policy_data)

    def delete_service_router_policy(self, policy_id: str):
        """Deletes a service router policy."""
        self._delete_entity("service-edge-router-policies", policy_id)
