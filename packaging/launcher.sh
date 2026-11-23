#!/bin/bash
# launcher.sh: the launcher for eval-coach on a Mac.
# Finds Python 3.9 or later, or installs a private copy after asking, then
# starts the app. tools/build_pyz.py ships this script as dist/eval-coach.command
# with the app archive appended after the marker line at the end, so the app
# runs from this file itself.
#
# Rules for editing this file:
#  - Plain ASCII with LF line endings, and only features of bash 3.2 (the bash
#    every Mac has): no associative arrays, no ${var,,}, no mapfile.
#  - Every path through the script must end in exit, so bash never reads the
#    archive that follows the marker line. All work happens inside functions
#    and the last command before the marker is "exit".
#  - Call system tools by full path. Other programs can shadow them on PATH.
#  - Quote every path. Nothing is passed through eval.
#  - Messages call the file "eval-coach", never by its file name.
#  - The pinned values below are stamped from packaging/runtime-manifest.json
#    by tools/build_pyz.py. No environment value changes a required hash.

EC_PY_VERSION="3.13.18"
EC_PY_RELEASE="20261110"
EC_PY_ARM64_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.13.18%2B20261110-aarch64-apple-darwin-install_only.tar.gz"
EC_PY_ARM64_SHA256="1afd3983237c2a10277345f235be730e9cb49a123e0574ed252dbf3a841a24e4"
EC_PY_ARM64_BYTES="25598083"
EC_PY_X64_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.13.18%2B20261110-x86_64-apple-darwin-install_only.tar.gz"
EC_PY_X64_SHA256="a46bcdeecd28ba253522b321dcb3806da1b0ff581479fc1d27e9613e3ac44764"
EC_PY_X64_BYTES="25349864"

EC_MIN_MACOS=13
EC_PROBE_TIMEOUT=10
EC_PY=""
EC_BROKEN=""
EC_WORK=""
EC_URL=""
EC_SHA256=""
EC_BYTES=""

say() {
  printf '%s\n' "$1"
}

blank() {
  printf '\n'
}

hold() {
  # Keeps a double-clicked window open so the message can be read.
  blank
  printf 'Press any key to close this window.'
  read -n 1 -s -r
  blank
}

cleanup() {
  if [ -n "$EC_WORK" ] && [ -d "$EC_WORK" ]; then
    rm -rf "$EC_WORK" >/dev/null 2>&1
  fi
}

stop_with() {
  cleanup
  hold
  exit 1
}

# Sets EC_URL, EC_SHA256 and EC_BYTES for the chip the Python will run on.
# $1 is the output of uname -m, $2 is the value of sysctl sysctl.proc_translated
# (1 under Rosetta, which means the Mac itself is Apple Silicon).
pick_pin() {
  local machine="$1" translated="$2"
  if [ "$machine" = "arm64" ] || [ "$translated" = "1" ]; then
    EC_URL="$EC_PY_ARM64_URL"
    EC_SHA256="$EC_PY_ARM64_SHA256"
    EC_BYTES="$EC_PY_ARM64_BYTES"
  else
    EC_URL="$EC_PY_X64_URL"
    EC_SHA256="$EC_PY_X64_SHA256"
    EC_BYTES="$EC_PY_X64_BYTES"
  fi
}

# Succeeds when the macOS version text in $1 (for example 14.5) is $2 or later.
macos_at_least() {
  local version="$1" minimum="$2" major
  major="${version%%.*}"
  case "$major" in
    ''|*[!0-9]*) return 0 ;;
  esac
  [ "$major" -ge "$minimum" ]
}

# Tests the candidate in $1. Sets EC_PY on success. A candidate counts only when
# it prints a per-run token and reports Python 3.9 or later. It runs with
# arguments only, stdin from /dev/null, in an empty folder, and is stopped after
# a hard timeout.
probe() {
  local cand="$1" token out pid ticks line1 line2
  [ -x "$cand" ] || return 1
  token="EC${RANDOM}${RANDOM}"
  out="$EC_WORK/$token.out"
  (
    cd "$EC_WORK" || exit 1
    exec "$cand" -c "import sys; sys.version_info >= (3, 9) or sys.exit(1); print('$token'); print(sys.executable)" </dev/null >"$out" 2>/dev/null
  ) &
  pid=$!
  ticks=0
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$ticks" -ge $((EC_PROBE_TIMEOUT * 10)) ]; then
      kill -9 "$pid" >/dev/null 2>&1
      wait "$pid" >/dev/null 2>&1
      return 1
    fi
    sleep 0.1
    ticks=$((ticks + 1))
  done
  wait "$pid" >/dev/null 2>&1
  [ -f "$out" ] || return 1
  line1=""
  line2=""
  { IFS= read -r line1; IFS= read -r line2; } <"$out"
  [ "$line1" = "$token" ] || return 1
  EC_PY="$cand"
  return 0
}

# True when /usr/bin/python3 is Apple's stub: running it without the Command
# Line Tools opens Apple's installer, so it is never run in that case.
apple_stub_unsafe() {
  [ "$1" = "/usr/bin/python3" ] || return 1
  if /usr/bin/xcode-select -p >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

find_python() {
  local name cand list
  for name in python3 python; do
    list="$(type -ap "$name" 2>/dev/null)"
    while IFS= read -r cand; do
      [ -n "$cand" ] || continue
      apple_stub_unsafe "$cand" && continue
      probe "$cand" && return 0
    done <<EOF
$list
EOF
  done
  # For tests: only the PATH is searched, so the usual install folders cannot hide the case being tested.
  if [ "${EVAL_COACH_PATH_ONLY:-}" = "1" ]; then
    return 1
  fi
  for cand in \
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3"; do
    probe "$cand" && return 0
  done
  return 1
}

# Sets EC_FREE_MB to the free space on the drive that holds the home folder,
# or leaves it empty when that cannot be read.
free_space() {
  local kb
  EC_FREE_MB=""
  kb="$(/bin/df -k "$HOME" 2>/dev/null | /usr/bin/awk 'NR==2 {print $4}')"
  case "$kb" in
    ''|*[!0-9]*) return 0 ;;
  esac
  EC_FREE_MB=$((kb / 1024))
}

# Asks the install question up to three times. Sets EC_REPLY to yes or no.
ask() {
  local tries=0 answer
  EC_REPLY="no"
  while [ "$tries" -lt 3 ]; do
    tries=$((tries + 1))
    answer=""
    printf 'Install it now? Type Y or N, then press Enter: '
    if ! IFS= read -r answer; then
      blank
      return 0
    fi
    case "$answer" in
      Y|y|YES|Yes|yes) EC_REPLY="yes"; return 0 ;;
      N|n|NO|No|no) EC_REPLY="no"; return 0 ;;
    esac
    if [ "$tries" -lt 3 ]; then
      say "Please type Y for yes or N for no."
    fi
  done
  return 0
}

fail_network() {
  blank
  say "Python could not be downloaded (download tool code $1)."
  say "This computer is probably offline, or the company network or a proxy is"
  say "blocking the download. Nothing was installed."
  blank
  say "What to do next:"
  say "  1. Check your internet connection, then start eval-coach again."
  say "  2. If it still fails, the network is blocking the download. Install"
  say "     Python 3.9 or later from python.org or your company's software"
  say "     portal, then start eval-coach again."
  stop_with
}

fail_timeout() {
  blank
  say "The Python download took too long and timed out. Nothing was installed."
  blank
  say "What to do next:"
  say "  1. Start eval-coach again, ideally on a faster or more stable connection."
  say "  2. If it times out again, install Python 3.9 or later from python.org or"
  say "     your company's software portal, then start eval-coach again."
  stop_with
}

fail_disk_write() {
  blank
  say "The Python download could not be saved. The drive is probably full."
  say "Nothing was installed."
  blank
  say "What to do next: free up at least 150 MB on this drive, then start"
  say "eval-coach again."
  stop_with
}

fail_disk() {
  blank
  say "Not enough free disk space. Python needs about 150 MB in total and this"
  say "drive has only $1 MB free. Nothing was installed."
  blank
  say "What to do next: free up at least 150 MB on this drive, then start"
  say "eval-coach again."
  stop_with
}

fail_hash() {
  blank
  say "The downloaded Python file failed its safety check."
  say "Its SHA-256 fingerprint does not match the value built into eval-coach, so"
  say "the file is damaged or was changed on the way. It has been deleted and"
  say "nothing was installed. This check cannot be turned off."
  blank
  say "What to do next:"
  say "  1. Start eval-coach again to download a fresh copy."
  say "  2. If it fails again, the network is altering the download. Install"
  say "     Python 3.9 or later from python.org or your company's software"
  say "     portal, then start eval-coach again."
  stop_with
}

fail_cannot_verify() {
  blank
  say "The downloaded Python file could not be checked, so it was deleted and"
  say "nothing was installed. Unchecked files are never used."
  blank
  say "What to do next:"
  say "  1. Start eval-coach again."
  say "  2. If it fails again, install Python 3.9 or later from python.org or"
  say "     your company's software portal, then start eval-coach again."
  stop_with
}

fail_extract() {
  blank
  say "The Python files could not be unpacked. The drive may be full, or"
  say "security software may be blocking the files. Nothing was installed."
  blank
  say "What to do next:"
  say "  1. Free up at least 150 MB on this drive, then start eval-coach again."
  say "  2. If it fails again, install Python 3.9 or later from python.org or"
  say "     your company's software portal, then start eval-coach again."
  stop_with
}

fail_removed() {
  blank
  say "A Python file disappeared or would not run right after it was saved."
  say "Security software on this computer most likely removed or blocked it."
  say "Python was not installed."
  blank
  say "What to do next:"
  say "  1. Start eval-coach again."
  say "  2. If it fails again, install Python 3.9 or later from python.org or"
  say "     your company's software portal, then start eval-coach again."
  stop_with
}

fail_replace() {
  blank
  say "The old private copy of Python could not be replaced because something is"
  say "still using it. It is in this folder:"
  say "         $EC_RUNTIME"
  blank
  say "What to do next: close every eval-coach window, then start eval-coach again."
  stop_with
}

fail_folder() {
  blank
  say "This folder could not be created, so Python could not be installed:"
  say "         $EC_RUNTIME"
  blank
  say "What to do next: check that the drive is not full, then start eval-coach"
  say "again. If it still fails, install Python 3.9 or later from python.org or"
  say "your company's software portal, then start eval-coach again."
  stop_with
}

fail_tools() {
  blank
  say "This Mac is missing system tools eval-coach needs to download Python"
  say "(curl, tar and shasum). Nothing was installed."
  blank
  say "What to do next: install Python 3.9 or later from python.org or your"
  say "company's software portal, then start eval-coach again."
  stop_with
}

fail_temp() {
  blank
  say "eval-coach could not create a temporary folder."
  blank
  say "What to do next: free up some space on this drive, then start eval-coach"
  say "again."
  stop_with
}

fail_old_macos() {
  blank
  say "This version of macOS ($1) is not supported. eval-coach needs macOS $EC_MIN_MACOS"
  say "or later. Nothing was downloaded."
  blank
  say "What to do next: update macOS in System Settings, then start eval-coach"
  say "again."
  stop_with
}

declined() {
  cleanup
  blank
  say "Nothing was installed and nothing on this computer changed."
  blank
  say "eval-coach cannot start without Python. What to do next, either:"
  say "  - start eval-coach again and answer Y to install the private copy, or"
  say "  - install Python 3.9 or later from python.org or your company's software"
  say "    portal, then start eval-coach again."
  hold
  exit 0
}

install_private_python() {
  local archive actual rc
  [ -x /usr/bin/curl ] && [ -x /usr/bin/tar ] && [ -x /usr/bin/shasum ] || fail_tools
  free_space

  blank
  say "eval-coach needs Python 3.9 or later, and no working copy was found."
  if [ -n "$EC_BROKEN" ]; then
    say "A private copy from an earlier run is damaged, so it will be replaced."
  fi
  blank
  say "It can install a private copy of Python that only eval-coach uses:"
  blank
  say "  What:  Python $EC_PY_VERSION, a build for this Mac from python-build-standalone"
  say "  Size:  about $((EC_BYTES / 1000000)) MB to download, about 70 MB once installed"
  say "  Where:"
  say "         $EC_RUNTIME"
  say "  Download address:"
  say "         $EC_URL"
  if [ -n "$EC_FREE_MB" ]; then
    say "  Free space on this drive: $EC_FREE_MB MB"
  fi
  blank
  say "No administrator rights are needed. Your PATH and your other programs are"
  say "not changed."
  blank

  if [ -n "$EC_FREE_MB" ] && [ "$EC_FREE_MB" -lt 150 ]; then
    fail_disk "$EC_FREE_MB"
  fi

  ask
  [ "$EC_REPLY" = "yes" ] || declined

  mkdir -p "$EC_RUNTIME" >/dev/null 2>&1
  [ -d "$EC_RUNTIME" ] || fail_folder
  # Work inside the runtime folder with short relative names, so the system
  # tools never have to handle unusual characters in the home folder path.
  cd "$EC_RUNTIME" || fail_folder
  archive="python-$EC_PY_VERSION.tar.gz"
  rm -f "$archive" >/dev/null 2>&1

  blank
  say "Downloading Python $EC_PY_VERSION..."
  /usr/bin/curl --fail --location --connect-timeout 30 --max-time 900 --retry 2 --retry-delay 3 --progress-bar --output "$archive" "$EC_URL"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    rm -f "$archive" >/dev/null 2>&1
    case "$rc" in
      28) fail_timeout ;;
      23) fail_disk_write ;;
      *) fail_network "$rc" ;;
    esac
  fi
  [ -f "$archive" ] || fail_removed

  say "Checking the download against its pinned SHA-256 fingerprint..."
  actual="$(/usr/bin/shasum -a 256 "$archive" 2>/dev/null)"
  actual="${actual%% *}"
  if [ -z "$actual" ]; then
    rm -f "$archive" >/dev/null 2>&1
    fail_cannot_verify
  fi
  actual="$(printf '%s' "$actual" | /usr/bin/tr 'A-F' 'a-f')"
  if [ "$actual" != "$EC_SHA256" ]; then
    rm -f "$archive" >/dev/null 2>&1
    fail_hash
  fi

  say "Unpacking..."
  rm -rf "python.new" >/dev/null 2>&1
  mkdir "python.new" >/dev/null 2>&1
  if ! /usr/bin/tar -xzf "$archive" -C "python.new" >/dev/null 2>&1; then
    rm -rf "python.new" >/dev/null 2>&1
    rm -f "$archive" >/dev/null 2>&1
    fail_extract
  fi
  if [ ! -x "python.new/python/bin/python3" ]; then
    rm -rf "python.new" >/dev/null 2>&1
    rm -f "$archive" >/dev/null 2>&1
    fail_removed
  fi

  # Run the new copy before putting it in place.
  EC_PY=""
  if ! probe "$EC_RUNTIME/python.new/python/bin/python3"; then
    rm -rf "python.new" >/dev/null 2>&1
    rm -f "$archive" >/dev/null 2>&1
    fail_removed
  fi
  EC_PY=""
  if [ -d "python" ]; then
    rm -rf "python" >/dev/null 2>&1
    if [ -d "python" ]; then
      rm -rf "python.new" >/dev/null 2>&1
      rm -f "$archive" >/dev/null 2>&1
      fail_replace
    fi
  fi
  mv "python.new/python" "python" >/dev/null 2>&1
  rm -rf "python.new" >/dev/null 2>&1
  rm -f "$archive" >/dev/null 2>&1
  [ -x "$EC_PRIVATE" ] || fail_removed
  EC_PY="$EC_PRIVATE"
  say "Python $EC_PY_VERSION is installed."
}

main() {
  local version machine translated self name dir

  trap cleanup EXIT

  version="$(/usr/bin/sw_vers -productVersion 2>/dev/null)"
  macos_at_least "$version" "$EC_MIN_MACOS" || fail_old_macos "$version"

  machine="$(/usr/bin/uname -m 2>/dev/null)"
  translated="$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null)"
  pick_pin "$machine" "$translated"

  # The file's own full path, whatever characters its folder has.
  self="$0"
  case "$self" in
    /*) ;;
    *) self="$PWD/$self" ;;
  esac
  name="${self##*/}"
  dir="${self%/*}"
  dir="$(cd -P "$dir" 2>/dev/null && pwd -P)"
  EC_PYZ="$dir/$name"

  EC_HOME="$HOME/.eval-coach"
  EC_RUNTIME="$EC_HOME/runtime"
  EC_PRIVATE="$EC_RUNTIME/python/bin/python3"

  # For tests: EVAL_COACH_PYTHON_URL may point at a local copy of the archive.
  # It changes where the file comes from, never the hash it must match.
  if [ -n "${EVAL_COACH_PYTHON_URL:-}" ]; then
    EC_URL="$EVAL_COACH_PYTHON_URL"
  fi

  EC_WORK="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/ec-setup.XXXXXX" 2>/dev/null)"
  [ -n "$EC_WORK" ] && [ -d "$EC_WORK" ] || fail_temp

  say "Looking for Python 3.9 or later..."

  if ! find_python; then
    if [ -e "$EC_PRIVATE" ]; then
      if ! probe "$EC_PRIVATE"; then
        EC_BROKEN="1"
      fi
    fi
    if [ -z "$EC_PY" ]; then
      install_private_python
    fi
  fi

  cleanup
  blank
  say "Starting eval-coach. Keep this window open while you use it."
  blank
  "$EC_PY" -B "$EC_PYZ" --python "$EC_PY" "$@"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    blank
    say "eval-coach stopped because of a problem (code $rc)."
    say "The lines above this message say what went wrong."
    blank
    say "What to do next: close this window and start eval-coach again."
    hold
  fi
  exit "$rc"
}

# A test can load the functions without running anything.
if [ "${EC_SOURCE_ONLY:-}" = "1" ]; then
  return 0 2>/dev/null || exit 0
fi

main "$@"
exit $?
# ===== eval-coach.pyz follows =====
