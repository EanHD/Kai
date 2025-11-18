#!/usr/bin/env python3
"""Quick test script to verify HTTPS configuration is working."""

import os
import sys
import yaml


def test_https_config():
    """Test HTTPS configuration and certificate files."""
    print("🔍 Testing HTTPS Configuration\n")
    
    # Check config file
    config_path = "config/api.yaml"
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return False
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    ssl_config = config.get('server', {}).get('ssl', {})
    
    print("📋 SSL Configuration:")
    print(f"   Enabled: {ssl_config.get('enabled', False)}")
    print(f"   Certfile: {ssl_config.get('certfile')}")
    print(f"   Keyfile: {ssl_config.get('keyfile')}")
    print(f"   CA Certs: {ssl_config.get('ca_certs')}\n")
    
    # Check certificate files exist
    certfile = ssl_config.get('certfile')
    keyfile = ssl_config.get('keyfile')
    
    if certfile and os.path.exists(certfile):
        print(f"✅ Certificate file exists: {certfile}")
    elif certfile:
        print(f"⚠️  Certificate file not found: {certfile}")
        print(f"   Run: ./scripts/generate_ssl_cert.sh")
    
    if keyfile and os.path.exists(keyfile):
        print(f"✅ Key file exists: {keyfile}")
        # Check permissions
        key_perms = oct(os.stat(keyfile).st_mode)[-3:]
        if key_perms == '600':
            print(f"   Permissions: {key_perms} ✓")
        else:
            print(f"   ⚠️  Permissions: {key_perms} (should be 600)")
            print(f"   Run: chmod 600 {keyfile}")
    elif keyfile:
        print(f"⚠️  Key file not found: {keyfile}")
        print(f"   Run: ./scripts/generate_ssl_cert.sh")
    
    print("\n✅ HTTPS configuration test complete!\n")
    
    if not ssl_config.get('enabled'):
        print("ℹ️  To enable HTTPS:")
        print("   1. Edit config/api.yaml")
        print("   2. Set server.ssl.enabled: true")
        print("   3. Restart the server with: python main.py\n")
    else:
        print("🔒 HTTPS is enabled!")
        print("   Server will use HTTPS when started with: python main.py\n")
    
    return True


if __name__ == "__main__":
    try:
        success = test_https_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
