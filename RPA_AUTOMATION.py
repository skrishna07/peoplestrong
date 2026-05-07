import sys
from modules.ERP_PULL import ERP_to_PS_Pull
from modules.PEOPLE_STRONG_PUSH import PS_to_ERP_Push


def _parse_limit(args):
    if len(args) < 3:
        return None

    try:
        value = int(args[2])
        return value if value > 0 else None
    except Exception:
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        max_ids = _parse_limit(sys.argv)
        if mode == "push":
            PS_to_ERP_Push(max_ids=max_ids)
        elif mode == "pull":
            ERP_to_PS_Pull(max_ids=max_ids)
        elif mode == "both":
            PS_to_ERP_Push(max_ids=max_ids)
            ERP_to_PS_Pull(max_ids=max_ids)
        else:
            print("Unknown mode. Use 'push', 'pull', or 'both'.")
    else:
        # Default behavior: only push
        PS_to_ERP_Push()
