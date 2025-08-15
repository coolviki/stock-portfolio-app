import json
import os
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ProviderPriority(Enum):
    """Provider priority levels"""
    PRIMARY = 1
    SECONDARY = 2
    TERTIARY = 3
    DISABLED = 999

class PriceProviderConfig:
    """Manages configuration for stock price providers"""
    
    def __init__(self, config_file: str = "price_provider_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
        default_config = {
            "version": "1.0",
            "providers": {
                "alpha_vantage": {
                    "enabled": True,
                    "priority": ProviderPriority.PRIMARY.value,
                    "config": {
                        "api_key": "",
                        "timeout": 10
                    }
                },
                "yahoo_finance": {
                    "enabled": True,
                    "priority": ProviderPriority.SECONDARY.value,
                    "config": {
                        "timeout": 10
                    }
                }
            },
            "waterfall": {
                "enabled": True,
                "retry_disabled_after_minutes": 60,
                "max_retries_per_provider": 3
            },
            "fallback": {
                "return_zero_on_failure": True,
                "cache_duration_minutes": 5
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                # Merge with defaults to ensure all keys exist
                merged_config = self._merge_config(default_config, config)
                logger.info(f"Loaded price provider config from {self.config_file}")
                return merged_config
            except Exception as e:
                logger.error(f"Error loading config file {self.config_file}: {e}")
                logger.info("Using default configuration")
                return default_config
        else:
            logger.info(f"Config file {self.config_file} not found, creating with defaults")
            self._save_config(default_config)
            return default_config
    
    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """Merge loaded config with defaults to ensure all keys exist"""
        merged = default.copy()
        
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_config(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def _save_config(self, config: Dict = None):
        """Save configuration to file"""
        config_to_save = config or self.config
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
            logger.info(f"Saved price provider config to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config file {self.config_file}: {e}")
    
    def get_provider_config(self, provider_name: str) -> Optional[Dict]:
        """Get configuration for a specific provider"""
        return self.config.get("providers", {}).get(provider_name)
    
    def update_provider_config(self, provider_name: str, config: Dict):
        """Update configuration for a specific provider"""
        if "providers" not in self.config:
            self.config["providers"] = {}
        
        self.config["providers"][provider_name] = config
        self._save_config()
        logger.info(f"Updated configuration for provider: {provider_name}")
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled providers in priority order"""
        providers = []
        
        for name, config in self.config.get("providers", {}).items():
            if config.get("enabled", False):
                priority = config.get("priority", ProviderPriority.DISABLED.value)
                providers.append((name, priority))
        
        # Sort by priority (lower number = higher priority)
        providers.sort(key=lambda x: x[1])
        return [name for name, _ in providers]
    
    def set_provider_priority(self, provider_name: str, priority: int):
        """Set priority for a provider"""
        if provider_name in self.config.get("providers", {}):
            self.config["providers"][provider_name]["priority"] = priority
            self._save_config()
            logger.info(f"Set priority {priority} for provider: {provider_name}")
    
    def enable_provider(self, provider_name: str):
        """Enable a provider"""
        if provider_name in self.config.get("providers", {}):
            self.config["providers"][provider_name]["enabled"] = True
            self._save_config()
            logger.info(f"Enabled provider: {provider_name}")
    
    def disable_provider(self, provider_name: str):
        """Disable a provider"""
        if provider_name in self.config.get("providers", {}):
            self.config["providers"][provider_name]["enabled"] = False
            self._save_config()
            logger.info(f"Disabled provider: {provider_name}")
    
    def set_api_key(self, provider_name: str, api_key: str):
        """Set API key for a provider"""
        if provider_name in self.config.get("providers", {}):
            if "config" not in self.config["providers"][provider_name]:
                self.config["providers"][provider_name]["config"] = {}
            
            self.config["providers"][provider_name]["config"]["api_key"] = api_key
            self._save_config()
            logger.info(f"Updated API key for provider: {provider_name}")
    
    def get_waterfall_config(self) -> Dict:
        """Get waterfall configuration"""
        return self.config.get("waterfall", {})
    
    def update_waterfall_config(self, config: Dict):
        """Update waterfall configuration"""
        self.config["waterfall"] = config
        self._save_config()
        logger.info("Updated waterfall configuration")
    
    def get_fallback_config(self) -> Dict:
        """Get fallback configuration"""
        return self.config.get("fallback", {})
    
    def export_config(self) -> Dict:
        """Export current configuration (without sensitive data)"""
        safe_config = self.config.copy()
        
        # Remove sensitive information
        for provider_name, provider_config in safe_config.get("providers", {}).items():
            if "config" in provider_config and "api_key" in provider_config["config"]:
                api_key = provider_config["config"]["api_key"]
                if api_key:
                    # Show only first and last 4 characters
                    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
                    safe_config["providers"][provider_name]["config"]["api_key"] = masked_key
                else:
                    safe_config["providers"][provider_name]["config"]["api_key"] = "Not Set"
        
        return safe_config
    
    def import_config(self, new_config: Dict):
        """Import configuration from external source"""
        try:
            # Validate basic structure
            if "providers" not in new_config:
                raise ValueError("Invalid config: missing 'providers' section")
            
            # Merge with current config to preserve any missing defaults
            merged_config = self._merge_config(self.config, new_config)
            
            # Save and reload
            self._save_config(merged_config)
            self.config = merged_config
            
            logger.info("Successfully imported new configuration")
            return True
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        
        self.config = self._load_config()
        logger.info("Reset configuration to defaults")

# Global configuration instance
price_config = PriceProviderConfig()