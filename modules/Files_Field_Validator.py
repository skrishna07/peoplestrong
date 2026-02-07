from libraries import *
from modules.Helpers import *

def load_file_mapping_config(config_path="mapping.json"):
    """Loads the JSON rulebook with a fallback for flat or nested structures."""
    try:
        if not os.path.exists(config_path):
            logging.warning(f"⚠️ Mapping file {config_path} not found.")
            return {}
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            
            # 1. Try to get nested rules first
            rules = config.get("file_mapping_rules")
            
            # 2. If it's None (meaning it's a flat JSON), use the whole config
            if rules is None:
                rules = config
            
            logging.info(f"✅ Successfully loaded {len(rules)} mapping rules from {config_path}")
            return rules
            
    except Exception as e:
        logging.error(f"❌ Failed to parse mapping.json: {str(e)}")
        return {}










