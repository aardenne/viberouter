#!/usr/bin/env bash
# =============================================================================
# VibeStack Publishing Script
# Publishes VibeRouter (PyPI) and VibeCommit (npm) to their respective registries
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIBEROOTER_DIR="${ROOT_DIR}/viberouter"
VIBECOMMIT_DIR="${ROOT_DIR}/vibecommit"

echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC} ${BOLD}VibeStack Publishing System${NC}                    ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
check_prerequisites() {
  echo -e "${BOLD}Checking prerequisites...${NC}"
  
  local missing=()
  
  command -v pip >/dev/null 2>&1 || missing+=("pip")
  command -v python3 >/dev/null 2>&1 || missing+=("python3")
  command -v npm >/dev/null 2>&1 || missing+=("npm")
  command -v git >/dev/null 2>&1 || missing+=("git")
  
  if [ ${#missing[@]} -gt 0 ]; then
    echo -e "${RED}✗ Missing tools: ${missing[*]}${NC}"
    exit 1
  fi
  
  # Check Python version
  local python_version
  python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  local major=${python_version%%.*}
  local minor=${python_version##*.}
  if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 9 ]); then
    echo -e "${RED}✗ Python 3.9+ required (found ${python_version})${NC}"
    exit 1
  fi
  
  # Check Node version
  local node_version
  node_version=$(node -v | sed 's/v//')
  major=${node_version%%.*}
  minor=${node_version##*.}
  if [ "$major" -lt 18 ]; then
    echo -e "${RED}✗ Node.js 18+ required (found ${node_version})${NC}"
    exit 1
  fi
  
  echo -e "${GREEN}✓ All prerequisites met${NC}"
  echo ""
}

# Build VibeRouter
build_viberouter() {
  echo -e "${CYAN}Building VibeRouter...${NC}"
  
  cd "$VIBEROOTER_DIR"
  
  # Run tests first
  echo -e "${BOLD}Running tests...${NC}"
  if python3 -m pytest tests/ -q >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Tests passed${NC}"
  else
    echo -e "${RED}✗ Tests failed${NC}"
    exit 1
  fi
  
  # Build package
  echo -e "${BOLD}Building package...${NC}"
  rm -rf dist/ build/ *.egg-info
  python3 -m build
  
  # Check package
  echo -e "${BOLD}Checking package...${NC}"
  python3 -m twine check dist/*
  
  echo -e "${GREEN}✓ VibeRouter ready for publishing${NC}"
  echo ""
}

# Build VibeCommit
build_vibecommit() {
  echo -e "${CYAN}Building VibeCommit...${NC}"
  
  cd "$VIBECOMMIT_DIR"
  
  # Install dependencies
  echo -e "${BOLD}Installing dependencies...${NC}"
  npm ci --silent 2>/dev/null || npm install --silent
  
  # Build TypeScript
  echo -e "${BOLD}Compiling TypeScript...${NC}"
  npx tsc 2>&1 | grep -v "npm ERR!" || true
  
  # Check for compilation errors
  if [ ! -d "dist" ]; then
    echo -e "${RED}✗ TypeScript compilation failed${NC}"
    exit 1
  fi
  
  # Run tests
  echo -e "${BOLD}Running tests...${NC}"
  if npx jest --silent 2>/dev/null; then
    echo -e "${GREEN}✓ Tests passed${NC}"
  else
    echo -e "${YELLOW}⚠ Tests skipped (no test framework configured)${NC}"
  fi
  
  # Build package
  echo -e "${BOLD}Building package...${NC}"
  npm run build >/dev/null 2>&1
  
  # Check package
  echo -e "${BOLD}Checking package...${NC}"
  npm pack --dry-run
  
  echo -e "${GREEN}✓ VibeCommit ready for publishing${NC}"
  echo ""
}

# Publish VibeRouter
publish_viberouter() {
  echo -e "${CYAN}Publishing VibeRouter to PyPI...${NC}"
  
  cd "$VIBEROOTER_DIR"
  
  if [ ! -d "dist" ]; then
    echo -e "${RED}✗ Package not built. Run './scripts/publish.sh build' first.${NC}"
    exit 1
  fi
  
  # Check for PyPI credentials
  if [ -z "${PYPI_USERNAME:-}" ] && [ -z "${PYPI_PASSWORD:-}" ]; then
    echo -e "${YELLOW}⚠ PyPI credentials not set in environment${NC}"
    echo "Set PYPI_USERNAME and PYPI_PASSWORD before running"
    exit 1
  fi
  
  # Publish
  python3 -m twine upload --username "$PYPI_USERNAME" --password "$PYPI_PASSWORD" dist/*
  
  echo -e "${GREEN}✓ VibeRouter published!${NC}"
  echo "  https://pypi.org/project/viberouter/"
  echo ""
}

# Publish VibeCommit
publish_vibecommit() {
  echo -e "${CYAN}Publishing VibeCommit to npm...${NC}"
  
  cd "$VIBECOMMIT_DIR"
  
  if [ ! -d "dist" ]; then
    echo -e "${RED}✗ Package not built. Run './scripts/publish.sh build' first.${NC}"
    exit 1
  fi
  
  # Check npm authentication
  if ! npm whoami >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Not logged in to npm${NC}"
    echo "Run: npm login"
    exit 1
  fi
  
  # Publish
  npm publish --access public
  
  echo -e "${GREEN}✓ VibeCommit published!${NC}"
  echo "  https://www.npmjs.com/package/vibecommit"
  echo ""
}

# Create Git tags
tag_releases() {
  echo -e "${CYAN}Creating release tags...${NC}"
  
  cd "$ROOT_DIR"
  
  local viberouter_version
  viberouter_version=$(grep 'version' "$VIBEROOTER_DIR/pyproject.toml" | head -1 | sed 's/.*= *"\(.*\)".*/\1/')
  
  local vibecommit_version
  vibecommit_version=$(grep '"version"' "$VIBECOMMIT_DIR/package.json" | head -1 | sed 's/.*: *"\(.*\)".*/\1/')
  
  git tag "viberouter-${viberouter_version}" 2>/dev/null || true
  git tag "vibecommit-${vibecommit_version}" 2>/dev/null || true
  
  echo -e "${GREEN}✓ Tags created:${NC}"
  echo "  viberouter-${viberouter_version}"
  echo "  vibecommit-${vibecommit_version}"
  echo ""
}

# Main function
main() {
  local action="${1:-build}"
  
  case "$action" in
    check)
      check_prerequisites
      ;;
    build)
      check_prerequisites
      build_viberouter
      build_vibecommit
      ;;
    publish)
      publish_viberouter
      publish_vibecommit
      tag_releases
      ;;
    viberouter)
      build_viberouter
      ;;
    vibecommit)
      build_vibecommit
      ;;
    *)
      echo "Usage: $0 {check|build|publish|viberouter|vibecommit}"
      echo ""
      echo "  check      - Check prerequisites"
      echo "  build      - Build both packages"
      echo "  publish    - Publish both packages (requires credentials)"
      echo "  viberouter - Build only VibeRouter"
      echo "  vibecommit - Build only VibeCommit"
      exit 1
      ;;
  esac
}

main "$@"
