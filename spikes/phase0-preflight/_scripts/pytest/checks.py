import sys, importlib
print("version", sys.version)
print("executable", sys.executable)
print("flags.isolated", sys.flags.isolated, "safe_path", sys.flags.safe_path)
print("sys.path", sys.path)
for m in ["ctypes","http.server","zipfile","json","ssl","sqlite3","venv","ensurepip","pip","tkinter","zipapp","urllib.request","subprocess","hashlib","lzma","bz2","socket","asyncio","unittest"]:
    try:
        importlib.import_module(m); print("import OK  ", m)
    except Exception as e:
        print("import FAIL", m, repr(e))
import ctypes, ssl
print("kernel32 tick>0:", ctypes.windll.kernel32.GetTickCount64 and True, "msvcrt strlen:", ctypes.cdll.msvcrt.strlen(b"abcd"))
print("ssl", ssl.OPENSSL_VERSION, "default certs:", ssl.create_default_context().cert_store_stats())
print("trivial script OK")
