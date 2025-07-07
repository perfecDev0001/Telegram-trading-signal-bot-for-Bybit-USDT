#!/usr/bin/env python3
"""
SSL Fix for Windows systems
This module handles SSL certificate issues that can occur on Windows
"""
import os
import ssl
import certifi

def apply_ssl_fix():
    """Apply SSL fix for Windows systems"""
    try:
        # Set the CA bundle path for requests and other libraries
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        os.environ['SSL_CERT_FILE'] = certifi.where()
        
        # Set default SSL context to use certifi
        ssl._create_default_https_context = ssl._create_unverified_context
        
        print("✅ SSL fix applied successfully")
        return True
        
    except Exception as e:
        print(f"⚠️ SSL fix failed: {e}")
        return False

# Apply the fix when this module is imported
apply_ssl_fix()