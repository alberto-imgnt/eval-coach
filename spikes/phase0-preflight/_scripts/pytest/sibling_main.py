try:
    import sibling_mod
    print("sibling import OK", sibling_mod.V)
except Exception as e:
    print("sibling import FAIL", repr(e))
