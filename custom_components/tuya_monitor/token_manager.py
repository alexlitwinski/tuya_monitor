"""Token manager for Tuya API."""
import logging
import time
import hashlib
import hmac
import base64
import uuid  # Adicionando importação do uuid

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

TUYA_REGION_ENDPOINTS = {
    "us": "https://openapi.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com"
}

def generate_sign(client_secret, token, t, method='HMAC-SHA256'):
    """Generate Tuya API signature."""
    message = f"{token}{t}"
    sign = hmac.new(
        client_secret.encode('utf-8'), 
        message.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest().upper()
    return sign

def generate_nonce():
    """Generate a random nonce string."""
    return str(uuid.uuid4())

async def refresh_tuya_token(session, client_id, client_secret, refresh_token, region="us"):
    """Refresh Tuya access token using the refresh token."""
    try:
        base_url = TUYA_REGION_ENDPOINTS.get(region, TUYA_REGION_ENDPOINTS["us"])
        refresh_url = f"{base_url}/v1.0/token/{refresh_token}"
        
        # Generate timestamp and signature
        timestamp = str(int(time.time() * 1000))
        nonce = generate_nonce()
        
        # Create string to sign and sign it
        string_to_sign = client_id + timestamp + nonce
        signature = hmac.new(
            client_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        sign_hex = base64.b64encode(signature).decode('utf-8')
        
        # Prepare headers
        headers = {
            "client_id": client_id,
            "sign": sign_hex,
            "t": timestamp,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }
        
        _LOGGER.debug(f"Attempting to refresh token with URL: {refresh_url}")
        
        async with async_timeout.timeout(10):
            async with session.get(refresh_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error(f"Token refresh failed with status {response.status}: {error_text}")
                    return None
                    
                data = await response.json()
                
                if not data.get("success", False):
                    error_msg = data.get("msg", "Unknown error")
                    _LOGGER.error(f"Token refresh failed: {error_msg}")
                    return None
                
                result = data.get("result", {})
                if not result:
                    _LOGGER.error("Empty result from token refresh")
                    return None
                
                access_token = result.get("access_token")
                refresh_token = result.get("refresh_token")
                expire_time = result.get("expire_time")
                
                _LOGGER.info(f"Successfully refreshed token. New token expires in {expire_time} seconds")
                
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expire_time": expire_time,
                    "expiration_time": int(time.time()) + int(expire_time)
                }
    
    except Exception as e:
        _LOGGER.error(f"Error refreshing Tuya token: {e}")
        return None

async def get_new_token(session, client_id, client_secret, region="us"):
    """Get a new token from Tuya API."""
    try:
        base_url = TUYA_REGION_ENDPOINTS.get(region, TUYA_REGION_ENDPOINTS["us"])
        token_url = f"{base_url}/v1.0/token?grant_type=1"
        
        # Generate timestamp and signature
        timestamp = str(int(time.time() * 1000))
        nonce = generate_nonce()
        
        # Create string to sign and sign it
        string_to_sign = client_id + timestamp + nonce
        signature = hmac.new(
            client_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).digest()
        sign_hex = base64.b64encode(signature).decode('utf-8')
        
        # Prepare headers and body
        headers = {
            "client_id": client_id,
            "sign": sign_hex,
            "t": timestamp,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }
        
        _LOGGER.debug(f"Attempting to get new token with URL: {token_url}")
        _LOGGER.debug(f"Headers: {headers}")
        
        async with async_timeout.timeout(10):
            async with session.get(token_url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error(f"Get token failed with status {response.status}: {error_text}")
                    return None
                    
                data = await response.json()
                _LOGGER.debug(f"Token response: {data}")
                
                if not data.get("success", False):
                    error_msg = data.get("msg", "Unknown error")
                    _LOGGER.error(f"Get token failed: {error_msg}")
                    return None
                
                result = data.get("result", {})
                if not result:
                    _LOGGER.error("Empty result from get token")
                    return None
                
                access_token = result.get("access_token")
                refresh_token = result.get("refresh_token")
                expire_time = result.get("expire_time")
                
                _LOGGER.info(f"Successfully obtained new token. Token expires in {expire_time} seconds")
                
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expire_time": expire_time,
                    "expiration_time": int(time.time()) + int(expire_time)
                }
    
    except Exception as e:
        _LOGGER.error(f"Error getting new Tuya token: {e}")
        return None
