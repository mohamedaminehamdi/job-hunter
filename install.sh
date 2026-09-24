#!/bin/sh
# Install the jobhunt skills into whichever coding agent you use.
#
#   ./install.sh                     from a clone
#   curl -fsSL <raw-url> | sh        from anywhere
#   ./install.sh --list              show what would be installed, change nothing
#   ./install.sh --to ~/.claude      install somewhere specific
#   ./install.sh --only jobhunt-guard,jobhunt-fit
#   ./install.sh --uninstall
#
# JOBHUNT_SOURCE=/path/to/clone  copies from a checkout you already have
# rather than downloading.
#
# POSIX sh on purpose: /bin/sh is dash on Debian and bash on macOS, and this
# has to run on both without anybody choosing an interpreter. No bashisms, no
# arrays, no `local` outside functions that declare it.

set -eu

REPO="mohamedaminehamdi/job-hunter"
BRANCH="main"
SKILLS="jobhunt jobhunt-profile jobhunt-posting jobhunt-fit jobhunt-tailor \
jobhunt-letter jobhunt-guard jobhunt-answer jobhunt-pdf jobhunt-outreach \
jobhunt-critique"

only=""
target=""
mode="install"
source_dir=""

# Colour only when a person is watching. Piped into a file or a log, the escape
# codes are noise.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  bold=$(printf '\033[1m'); dim=$(printf '\033[2m')
  green=$(printf '\033[32m'); red=$(printf '\033[31m'); off=$(printf '\033[0m')
else
  bold=''; dim=''; green=''; red=''; off=''
fi

say()  { printf '%s\n' "$*"; }
step() { printf '  %s%s%s\n' "$green" "$*" "$off"; }
warn() { printf '  %s%s%s\n' "$red" "$*" "$off" >&2; }
die()  { printf '\n%serror:%s %s\n' "$red" "$off" "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Install the jobhunt skills.

  --list           show what would be installed and where, change nothing
  --to DIR         install into DIR/skills (e.g. --to ~/.claude)
  --only A,B       install only these skills (default: all eleven)
  --uninstall      remove them again
  --help

With no options it finds every coding agent you have and installs into each.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --list)      mode="list" ;;
    --uninstall) mode="uninstall" ;;
    --to)        target="${2:-}"; shift; [ -n "$target" ] || die "--to needs a directory" ;;
    --to=*)      target="${1#--to=}" ;;
    --only)      only="${2:-}"; shift; [ -n "$only" ] || die "--only needs skill names" ;;
    --only=*)    only="${1#--only=}" ;;
    -h|--help)   usage; exit 0 ;;
    *)           die "unknown option: $1  (try --help)" ;;
  esac
  shift
done

# --- what to install -------------------------------------------------------

if [ -n "$only" ]; then
  chosen=$(printf '%s' "$only" | tr ',' ' ')
  for want in $chosen; do
    found=0
    for known in $SKILLS; do [ "$want" = "$known" ] && found=1; done
    [ "$found" = 1 ] || die "no skill called '$want'. Available: $SKILLS"
  done
else
  chosen="$SKILLS"
fi

# --- where the files come from ---------------------------------------------

find_source() {
  # A checkout to copy from, if there is one. JOBHUNT_SOURCE points at a clone
  # somewhere else - it is how the download path is tested without pushing, and
  # it is useful to anyone who already has the repo.
  if [ -n "${JOBHUNT_SOURCE:-}" ]; then
    [ -d "$JOBHUNT_SOURCE/plugins/jobhunt/skills/jobhunt" ] \
      || die "JOBHUNT_SOURCE=$JOBHUNT_SOURCE has no plugins/jobhunt/skills in it"
    printf '%s' "$JOBHUNT_SOURCE/plugins/jobhunt/skills"
    return 0
  fi
  # A clone next to this script.
  self=$(dirname "$0" 2>/dev/null) || self="."
  case "$self" in /*) ;; *) self="$PWD/$self" ;; esac
  if [ -d "$self/plugins/jobhunt/skills/jobhunt" ]; then
    printf '%s' "$self/plugins/jobhunt/skills"
    return 0
  fi
  return 1
}

download_source() {
  # Piped from curl, so there is no clone. Fetch a tarball into a temp dir.
  command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 \
    || die "need curl or wget to download the skills"
  command -v tar >/dev/null 2>&1 || die "need tar to unpack the download"

  tmp=$(mktemp -d 2>/dev/null || mktemp -d -t jobhunt)
  url="https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$tmp/src.tar.gz" || die "could not download from $url"
  else
    wget -qO "$tmp/src.tar.gz" "$url" || die "could not download from $url"
  fi
  tar -xzf "$tmp/src.tar.gz" -C "$tmp" || die "the download did not unpack"
  inner=$(find "$tmp" -maxdepth 1 -type d -name 'job-hunter-*' | head -1)
  [ -d "$inner/plugins/jobhunt/skills" ] || die "the download has no skills in it"
  printf '%s' "$inner/plugins/jobhunt/skills"
}

# --- where the files go ----------------------------------------------------
#
# Only the agents with a real global skills directory are offered. Cursor,
# Cline and Windsurf read skills per project, not per user, so installing
# globally for them would put files somewhere they never look - the site
# explains the project-level route for those instead.

homes_for() {
  if [ -n "$target" ]; then
    # ~ expands, and a relative path is resolved against the working directory
    # so what gets printed is somewhere the reader can go and look.
    named=$(printf '%s' "$target" | sed "s|^~|$HOME|")
    case "$named" in /*) ;; *) named="$PWD/$named" ;; esac
    printf '%s|%s\n' "$named/skills" "the directory you named"
    return
  fi
  [ -d "$HOME/.claude" ]  && printf '%s|%s\n' "$HOME/.claude/skills" "Claude Code"
  [ -d "$HOME/.codex" ]   && printf '%s|%s\n' "$HOME/.codex/skills" "OpenAI Codex"
  [ -d "$HOME/.gemini" ]  && printf '%s|%s\n' "$HOME/.gemini/skills" "Gemini CLI"
  true
}

# Written to a file rather than piped into `while read`: a pipe puts the loop
# in a subshell, where `die` kills only the subshell and the script carries on
# to print "installed" after a copy that failed.
work=$(mktemp -d 2>/dev/null || mktemp -d -t jobhunt-install)
trap 'rm -rf "$work"' EXIT INT TERM
homes_for > "$work/destinations"
destinations=$(cat "$work/destinations")

if [ -z "$destinations" ]; then
  say ""
  warn "No coding agent found."
  say ""
  say "  Looked for ~/.claude, ~/.codex and ~/.gemini and found none of them."
  say ""
  say "  If you use Cursor, Cline or Windsurf, those read skills per project"
  say "  rather than per user. From inside your project:"
  say ""
  say "    ${bold}./install.sh --to .cursor${off}      (or .cline, or .windsurf)"
  say ""
  say "  Otherwise install one of the agents first, then run this again."
  exit 1
fi

# --- do it -----------------------------------------------------------------

count=0
for _ in $chosen; do count=$((count + 1)); done
noun="skills"; [ "$count" = 1 ] && noun="skill"

say ""
say "${bold}jobhunt${off} ${dim}- $count $noun, no API key, nothing to install${off}"
say ""

if [ "$mode" = "list" ]; then
  say "Would install:"
  for skill in $chosen; do say "  $skill"; done
  say ""
  say "Into:"
  while IFS='|' read -r dir label; do
    [ -n "$dir" ] && say "  $dir  ${dim}($label)${off}"
  done < "$work/destinations"
  say ""
  exit 0
fi

if [ "$mode" = "uninstall" ]; then
  while IFS='|' read -r dir label; do
    [ -n "$dir" ] || continue
    say "${bold}$label${off} ${dim}$dir${off}"
    for skill in $chosen; do
      if [ -d "${dir:?}/${skill:?}" ]; then
        rm -rf "${dir:?}/${skill:?}"
        step "removed $skill"
      fi
    done
    say ""
  done < "$work/destinations"
  say "Your ${bold}jobhunt/${off} folder was left alone - your CV and your runs are in it."
  say ""
  exit 0
fi

if ! source_dir=$(find_source); then
  say "${dim}Downloading...${off}"
  source_dir=$(download_source)
fi

for skill in $chosen; do
  [ -d "$source_dir/$skill" ] || die "$skill is missing from the source at $source_dir"
done

while IFS='|' read -r dir label; do
  [ -n "$dir" ] || continue
  say "${bold}$label${off} ${dim}$dir${off}"
  mkdir -p "$dir" || die "could not create $dir"
  for skill in $chosen; do
    # Copy beside the target and move into place, so an interrupted install
    # cannot leave half a skill where a working one used to be.
    # ${var:?} on every rm -rf: an empty $dir would otherwise make this
    # `rm -rf /jobhunt-guard`, and an installer must not be one bad read away
    # from that.
    rm -rf "${dir:?}/.${skill:?}.new"
    cp -R "$source_dir/$skill" "$dir/.$skill.new" \
      || die "could not copy $skill into $dir"
    # The agent may invoke a script directly rather than through python3.
    find "$dir/.$skill.new" -name '*.py' -exec chmod +x {} + 2>/dev/null || true
    rm -rf "${dir:?}/${skill:?}"
    mv "$dir/.$skill.new" "$dir/$skill" || die "could not install $skill into $dir"
    step "$skill"
  done
  say ""
done < "$work/destinations"

# --- what they need to know now --------------------------------------------

python_ok=0
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      python_ok=1
      break
    fi
  fi
done

browser_ok=0
for b in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "/Applications/Chromium.app/Contents/MacOS/Chromium" \
         "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
         "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"; do
  [ -x "$b" ] && browser_ok=1
done
for b in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge; do
  command -v "$b" >/dev/null 2>&1 && browser_ok=1
done

say "${bold}What it needs${off}"
if [ "$python_ok" = 1 ]; then
  step "Python 3.9+   already here"
else
  warn "Python 3.9+   not found - install it from python.org"
fi
if [ "$browser_ok" = 1 ]; then
  step "A browser     already here (for reading job pages and making PDFs)"
else
  warn "A browser     no Chrome, Chromium, Edge or Brave found."
  say "                 Without one you still get markdown; you do not get PDFs."
fi
say ""
say "${bold}Start${off}"
say "  Put your CV somewhere, open your agent, and say:"
say ""
say "      ${bold}prepare an application for <the job URL>${off}"
say ""
say "  It reads your CV once, writes ${bold}jobhunt/profile.yaml${off}, and asks you"
say "  to check it before anything is built on it."
say ""
say "${dim}It applies to nothing and sends nothing. You do that.${off}"
say ""
