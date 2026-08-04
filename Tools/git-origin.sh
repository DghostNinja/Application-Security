#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

check_origin() {
  if git remote get-url origin &>/dev/null; then
    echo -e "${GREEN}$(git remote get-url origin)${NC}"
    return 0
  else
    echo -e "${RED}none${NC}"
    return 1
  fi
}

show_menu() {
  clear
  echo "========================================"
  echo "       Git Origin URL Manager"
  echo "========================================"
  printf " Current origin: "
  check_origin || true
  echo "========================================"
  echo ""
  echo "  1)  Check origin URL"
  echo "  2)  Add origin URL"
  echo "  3)  Set/Change origin URL"
  echo "  4)  Remove origin"
  echo ""
  echo "  0)  Exit (or Ctrl+C)"
  echo ""
}

while true; do
  show_menu
  read -rp " Select option [0-4]: " choice

  case "$choice" in
    1)
      echo ""
      if git remote get-url origin &>/dev/null; then
        echo -e " Origin: ${GREEN}$(git remote get-url origin)${NC}"
      else
        echo -e " ${RED}No origin remote set.${NC}"
      fi
      ;;
    2)
      echo ""
      if git remote get-url origin &>/dev/null 2>&1; then
        echo -e " ${YELLOW}Origin already exists:${NC} $(git remote get-url origin)"
      else
        read -rp " Enter origin URL: " url
        if [ -n "$url" ]; then
          git remote add origin "$url"
          echo -e " ${GREEN}Added origin: $url${NC}"
        else
          echo -e " ${RED}No URL entered.${NC}"
        fi
      fi
      ;;
    3)
      echo ""
      read -rp " Enter new origin URL: " url
      if [ -z "$url" ]; then
        echo -e " ${RED}No URL entered.${NC}"
      elif git remote get-url origin &>/dev/null 2>&1; then
        old=$(git remote get-url origin)
        git remote set-url origin "$url"
        echo -e " ${GREEN}Updated:${NC} $old -> $url"
      else
        git remote add origin "$url"
        echo -e " ${GREEN}Added origin: $url${NC}"
      fi
      ;;
    4)
      echo ""
      if git remote get-url origin &>/dev/null 2>&1; then
        old=$(git remote get-url origin)
        echo -e " ${YELLOW}About to remove:${NC} $old"
        read -rp " Confirm removal? (y/N): " confirm
        if [[ "$confirm" =~ ^[yY] ]]; then
          git remote remove origin
          echo -e " ${GREEN}Removed origin:${NC} $old"
        else
          echo " Cancelled."
        fi
      else
        echo -e " ${RED}No origin remote to remove.${NC}"
      fi
      ;;
    0|q|quit|exit)
      echo ""
      exit 0
      ;;
    *)
      echo -e "\n ${RED}Invalid option.${NC}"
      ;;
  esac

  echo ""
  read -rp " Press Enter to continue..."
done
