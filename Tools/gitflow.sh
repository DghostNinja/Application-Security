#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

LOG="${GITFLOW_LOG:-$HOME/.barrel-gitflow.log}"
log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# ---------- tiny helpers ----------
say()    { echo -e "$*"; }
ok()     { echo -e "${GREEN}OK:${NC} $*"; }
warn()   { echo -e "${YELLOW}Note:${NC} $*"; }
err()    { echo -e "${RED}Error:${NC} $*" >&2; exit 1; }
# prompt  = yes by default (press Enter = yes)  -> for things you asked for
# prompt_no = no by default (press Enter = no) -> for destructive things
prompt()    { local a; IFS= read -rp "$* [Y/n]: " a; [[ -z "$a" || "$a" =~ ^[yY] ]]; }
prompt_no() { local a; IFS= read -rp "$* [y/N]: " a; [[ "$a" =~ ^[yY] ]]; }

inside_repo() { git rev-parse --is-inside-work-tree >/dev/null 2>&1; }
branch()      { git rev-parse --abbrev-ref HEAD; }
dirty()       { ! git diff --quiet || ! git diff --cached --quiet; }

check_origin() {
  if git remote get-url origin &>/dev/null; then
    echo -e "${GREEN}$(git remote get-url origin)${NC}"
    return 0
  else
    echo -e "${RED}none${NC}"
    return 1
  fi
}

# ---------- commands ----------
cmd_new() {
  local name="$1"
  if [ -z "$name" ]; then
    IFS= read -rp " Name your feature (no spaces, e.g. fix-logcat): " name
    [ -z "$name" ] && { warn "No name entered — cancelled."; return 1; }
  fi
  local br="feature/$name"
  if git show-ref --verify --quiet "refs/heads/$br"; then
    warn "Branch '$br' already exists. Try 'list' to see what you have."
    return 1
  fi
  if [ "$(branch)" != "main" ]; then
    warn "You're on '$(branch)'. I'll switch to main first."
    if dirty; then
      warn "You have unsaved work on '$(branch)'. Commit or stash it first."
      return 1
    fi
  fi
  git checkout main
  git pull
  git checkout -b "$br"
  ok "Now on '$br'. Edit files freely — 'main' stays untouched."
  log "new feature branch: $br"
}

cmd_push() {
  local br
  br="$(branch)"
  if [ "$br" = "main" ]; then
    warn "You're on 'main' — nothing to push here. Start a feature first (menu 1)."
    return 1
  fi
  if dirty; then
    say " ${YELLOW}You have unsaved changes — I'll commit them first.${NC}"
    IFS= read -rp " Commit message (e.g. 'fix logcat crash', Enter = default): " msg
    git add -A
    git commit -m "${msg:-chore: $br}"
    ok "Saved: ${msg:-chore: $br}"
  fi
  if ! git push -u origin "$br"; then
    warn "Push failed (check network/auth). Nothing was lost — your commits are local."
    log "push FAILED: $br"
    return 1
  fi
  ok "Pushed '$br' to GitHub. Branch pushes don't run any builds."
  log "pushed: $br"
}

cmd_finish() {
  local br
  br="$(branch)"
  [ "$br" = "main" ] && { warn "Already on main — start a feature to merge."; return 1; }
  if dirty; then
    warn "You have unsaved changes — they'll be committed as part of this."
  fi
  say " I'm about to: commit -> switch to main -> pull -> merge '$br' -> push -> delete '$br'."
  if ! prompt " Merge '$br' into main now?"; then
    say " Cancelled. Nothing changed."
    return 1
  fi
  git add -A
  if ! git diff --cached --quiet; then
    IFS= read -rp " Commit message (Enter = default): " msg
    git commit -m "${msg:-chore: ${br#feature/}}"
  fi
  git checkout main
  git pull
  if ! git merge "$br"; then
    warn "Merge conflicts happened. Fix them (or ask for help), then run 'finish' again."
    return 1
  fi
  if ! git push origin main; then
    warn "Push failed. Your merge is committed locally on main — try 'git push' later."
    return 1
  fi
  git branch -d "$br" 2>/dev/null || warn "Couldn't auto-delete '$br'."
  ok "Done! '$br' is now part of main and pushed to GitHub."
  log "merged $br -> main (pushed & branch deleted)"
}

cmd_status() {
  say " Branch: ${CYAN}$(branch)${NC}"
  if dirty; then
    say " You have unsaved changes here. Use menu 2 to commit & push them."
  else
    say " All clean — nothing unsaved."
  fi
}

cmd_history() {
  if [ -f "$LOG" ]; then
    echo "========================================"
    echo "        Recent activity"
    echo "        ($LOG)"
    echo "========================================"
    tail -n 30 "$LOG"
  else
    warn "No history yet — do something first."
  fi
}

cmd_list() {
  git branch -vv
}

cmd_history() {
  if [ ! -f "$LOG" ]; then
    warn "No history yet — the log is written to: $LOG"
    return 1
  fi
  echo " Most recent actions (newest first):"
  echo " ----------------------------------------"
  tail -n 30 "$LOG" | tac
  echo " ----------------------------------------"
  echo " Full log: $LOG"
}

cmd_undo() {
  if git rev-parse HEAD~1 >/dev/null 2>&1; then
    say " Most recent commit on $(branch):"
    git log --oneline -1
    if prompt " Roll it back (your FILES are kept, just un-committed)?"; then
      git reset --soft HEAD~1
      ok "Undone. Your changes are back as 'staged' — commit again anytime."
      log "undo last commit on $(branch)"
    else
      say " Cancelled."
    fi
  else
    warn "No previous commit to go back to."
  fi
}

# ---------- origin manager ----------
origin_menu() {
  while true; do
    echo ""
    echo "========================================"
    echo "       Remote Origin Manager"
    echo "========================================"
    printf " Current origin: "
    check_origin || true
    echo "========================================"
    echo "  1)  Check origin URL"
    echo "  2)  Add origin URL"
    echo "  3)  Set/Change origin URL"
    echo "  4)  Remove origin"
    echo "  0)  Back to main menu"
    IFS= read -rp " Choose [0-4]: " choice

    case "$choice" in
      1)
        if git remote get-url origin &>/dev/null; then
          printf " Origin: ${GREEN}%s${NC}\n" "$(git remote get-url origin)"
        else
          printf " ${RED}No origin remote set.${NC}\n"
        fi
        ;;
      2)
        if git remote get-url origin &>/dev/null 2>&1; then
          warn "Origin already exists: $(git remote get-url origin)"
        else
          IFS= read -rp " Enter origin URL (e.g. git@github.com:you/repo.git): " url
          if [ -n "$url" ]; then
            git remote add origin "$url"
            ok "Added origin: $url"
            log "origin added: $url"
          else
            warn "No URL entered."
          fi
        fi
        ;;
      3)
        IFS= read -rp " Enter new origin URL: " url
        if [ -z "$url" ]; then
          warn "No URL entered."
        elif git remote get-url origin &>/dev/null 2>&1; then
          local old
          old="$(git remote get-url origin)"
          git remote set-url origin "$url"
          ok "Updated: $old -> $url"
          log "origin changed: $old -> $url"
        else
          git remote add origin "$url"
          ok "Added origin: $url"
          log "origin added: $url"
        fi
        ;;
      4)
        if git remote get-url origin &>/dev/null 2>&1; then
          local old
          old="$(git remote get-url origin)"
          say " About to remove: ${YELLOW}$old${NC}"
          if prompt_no " Confirm removal?"; then
            git remote remove origin
            ok "Removed origin: $old"
            log "origin removed: $old"
          else
            say " Cancelled."
          fi
        else
          warn "No origin remote to remove."
        fi
        ;;
      0|q|quit|exit) return 0 ;;
      *) say " ${RED}Invalid option.${NC}" ;;
    esac
  done
}

# ---------- help ----------
show_help() {
  cat <<'EOF'

========================================
        Barrel Git Helper
========================================
 A friendly wrapper around git — no commands to memorize.
 Pick what you want to do and it does the safe thing.

 QUICK START
 --------------------------------------------------------
   ./gitflow.sh               open the interactive menu
   ./gitflow.sh --help        show this help
   ./gitflow.sh new my-thing  start a new feature branch
   ./gitflow.sh push          save & send your feature to GitHub
   ./gitflow.sh finish        merge your feature into main
   ./gitflow.sh status        "what am I working on?"
   ./gitflow.sh list          show every branch
   ./gitflow.sh undo          take back your last commit
   ./gitflow.sh origin        manage the GitHub remote URL
   ./gitflow.sh history       see everything you've done (even after quitting)
   ./gitflow.sh history       see everything you've done (persistent log)

 TIPS
 --------------------------------------------------------
   • Only ONE prompt is ever active — whatever it asks is
     what your Enter goes to. No hidden double-enters.
   • Pressing Enter usually means YES. Only destructive
     actions (like removing origin) need an explicit y.
   • '0' or 'q' at any menu goes back / exits.
   • Every action is saved to a log — 'history' shows it
     any time, even after the script is closed.
   • Every action is saved to ~/.barrel-gitflow.log, so you
     can run './gitflow.sh history' even after quitting.

 BRANCHES IN PLAIN ENGLISH
 --------------------------------------------------------
   main      = the official code. Nobody works here directly.
   feature/  = your personal copy. Edit, save, push here freely.
   Nothing reaches main until you run 'finish'.

 WHAT IT PROTECTS YOU FROM
 --------------------------------------------------------
   • 'push' can never push to main by accident.
   • 'new' always starts from the latest GitHub main.
   • 'finish' shows what it will do before doing it.
   • 'undo' keeps your files — only the commit is rolled back.

EOF
}

# ---------- main menu ----------
show_menu() {
  echo "========================================"
  echo "        Barrel Git Helper"
  echo "========================================"
  printf " Current branch: ${CYAN}%s${NC}\n" "$(branch)"
  printf " Remote origin:  "
  check_origin || true
  echo "========================================"
  echo ""
  echo "  1)  Start a new feature"
  echo "  2)  Save my work & push to GitHub"
  echo "  3)  Merge my feature into main (finish)"
  echo "  4)  What am I working on? (status)"
  echo "  5)  See all branches"
  echo "  6)  Undo my last commit"
  echo "  7)  Remote (origin) — check / add / change / remove"
  echo "  8)  See what I've done (history)"
  echo ""
  echo "  0)  Exit"
  echo ""
}

interactive() {
  clear
  while true; do
    show_menu
    IFS= read -rp " Choose a number [0-8]: " choice
    case "$choice" in
      1) cmd_new "" || true ;;
      2) cmd_push || true ;;
      3) cmd_finish || true ;;
      4) cmd_status ;;
      5) cmd_list ;;
      6) cmd_undo || true ;;
      7) origin_menu || true ;;
      8) cmd_history || true ;;
      0|q|quit|exit) exit 0 ;;
      *) say " ${RED}Not a valid choice.${NC}" ;;
    esac
    echo ""
  done
}

main() {
  inside_repo || err "Not inside a git repo — run this from the Barrel folder."
  case "${1:-menu}" in
    -h|--help|help) show_help ;;
    menu)           interactive ;;
    new)            cmd_new "${2:-}" ;;
    push)           cmd_push ;;
    finish)         cmd_finish ;;
    status)         cmd_status ;;
    list)           cmd_list ;;
    history|log)    cmd_history ;;
    undo)           cmd_undo ;;
    origin)         origin_menu ;;
    *)
      say " Unknown command: '$1'. Run './gitflow.sh --help'."
      exit 1
      ;;
  esac
}

main "$@"
