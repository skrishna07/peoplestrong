import sys
from modules.ERP_PULL import ERP_to_PS_Pull
from modules.PEOPLE_STRONG_PUSH import PS_to_ERP_Push

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "push":
            PS_to_ERP_Push()
        elif mode == "pull":
            ERP_to_PS_Pull()
        elif mode == "both":
            PS_to_ERP_Push()
            ERP_to_PS_Pull()
        else:
            print("Unknown mode. Use 'push', 'pull', or 'both'.")
    else:
        # Default behavior: only push
        PS_to_ERP_Push()
