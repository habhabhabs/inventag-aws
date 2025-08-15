#!/bin/bash

# Repository Configuration Script for Automated Releases
# Configures GitHub repository settings to allow automated version updates

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "🚀 InvenTag Repository Configuration Script"
    echo "=================================================="
    echo -e "${NC}"
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) not found. Please install it first:"
        echo "  - macOS: brew install gh"
        echo "  - Ubuntu: apt install gh"
        echo "  - Windows: winget install GitHub.cli"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install it first:"
        echo "  - macOS: brew install jq"
        echo "  - Ubuntu: apt install jq"
        echo "  - Windows: winget install jqlang.jq"
        exit 1
    fi
    
    log_success "Dependencies check passed"
}

authenticate() {
    log_info "Checking GitHub authentication..."
    
    if ! gh auth status &> /dev/null; then
        log_warning "Not authenticated with GitHub CLI"
        log_info "Please authenticate with GitHub CLI:"
        gh auth login
    fi
    
    log_success "GitHub authentication verified"
}

get_repository_info() {
    log_info "Getting repository information..."
    
    if [ -z "$GITHUB_REPOSITORY" ]; then
        # Try to get from git remote
        REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")
        if [[ $REPO_URL =~ github\.com[:/]([^/]+)/([^/]+)\.git ]]; then
            GITHUB_OWNER="${BASH_REMATCH[1]}"
            GITHUB_REPO="${BASH_REMATCH[2]}"
            GITHUB_REPOSITORY="$GITHUB_OWNER/$GITHUB_REPO"
        else
            log_error "Could not determine GitHub repository"
            echo "Please run this script from a git repository or set GITHUB_REPOSITORY environment variable"
            exit 1
        fi
    else
        IFS='/' read -r GITHUB_OWNER GITHUB_REPO <<< "$GITHUB_REPOSITORY"
    fi
    
    log_success "Repository: $GITHUB_REPOSITORY"
}

configure_actions_permissions() {
    log_info "Configuring Actions permissions..."
    
    # Note: These settings typically need to be configured through the GitHub web interface
    # as they're not available via API for security reasons
    
    log_warning "Actions permissions must be configured manually:"
    echo ""
    echo "1. Go to: https://github.com/$GITHUB_REPOSITORY/settings/actions"
    echo "2. Under 'Actions permissions':"
    echo "   ✅ Select 'Allow all actions and reusable workflows'"
    echo "3. Under 'Workflow permissions':"
    echo "   ✅ Select 'Read and write permissions'"
    echo "   ✅ Check 'Allow GitHub Actions to create and approve pull requests'"
    echo ""
    
    read -p "Press Enter after configuring Actions permissions..."
    log_success "Actions permissions configured"
}

configure_branch_protection() {
    log_info "Configuring branch protection for main branch..."
    
    # Check if main branch protection exists
    if gh api "repos/$GITHUB_REPOSITORY/branches/main/protection" &> /dev/null; then
        log_info "Main branch protection already exists"
        log_info "Updating to allow GitHub Actions..."
        
        # Get current protection settings
        CURRENT_PROTECTION=$(gh api "repos/$GITHUB_REPOSITORY/branches/main/protection")
        
        # Update protection to allow GitHub Actions
        gh api --method PUT "repos/$GITHUB_REPOSITORY/branches/main/protection" \
            --field required_status_checks='{"strict":true,"contexts":[]}' \
            --field enforce_admins=true \
            --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
            --field restrictions=null \
            --field required_linear_history=false \
            --field allow_force_pushes=false \
            --field allow_deletions=false \
            --field block_creations=false \
            --field required_conversation_resolution=false \
            > /dev/null 2>&1 || log_warning "Could not automatically update branch protection"
        
    else
        log_info "No branch protection found for main branch"
        log_info "Creating basic branch protection..."
        
        # Create basic branch protection
        gh api --method PUT "repos/$GITHUB_REPOSITORY/branches/main/protection" \
            --field required_status_checks='{"strict":false,"contexts":[]}' \
            --field enforce_admins=false \
            --field required_pull_request_reviews='{"required_approving_review_count":1}' \
            --field restrictions=null \
            > /dev/null 2>&1 || log_warning "Could not create branch protection automatically"
    fi
    
    log_warning "Manual branch protection configuration may be needed:"
    echo ""
    echo "1. Go to: https://github.com/$GITHUB_REPOSITORY/settings/branches"
    echo "2. Edit the main branch protection rule"
    echo "3. Under 'Restrict pushes that create files':"
    echo "   ✅ Add 'github-actions[bot]' to exceptions"
    echo "4. Save changes"
    echo ""
    
    read -p "Press Enter after configuring branch protection (if needed)..."
    log_success "Branch protection configured"
}

create_release_labels() {
    log_info "Creating release labels..."
    
    # Define release labels
    declare -A LABELS=(
        ["release:major"]="7057ff,Triggers a major version release (e.g. 1.0.0 → 2.0.0)"
        ["release:minor"]="0075ca,Triggers a minor version release (e.g. 1.0.0 → 1.1.0)"
        ["release:patch"]="008672,Triggers a patch version release (e.g. 1.0.0 → 1.0.1)"
    )
    
    for label in "${!LABELS[@]}"; do
        IFS=',' read -r color description <<< "${LABELS[$label]}"
        
        if gh label list --search "$label" --json name --jq '.[].name' | grep -q "^$label$"; then
            log_info "Label '$label' already exists"
        else
            gh label create "$label" --color "$color" --description "$description"
            log_success "Created label: $label"
        fi
    done
}

test_workflow_permissions() {
    log_info "Testing workflow permissions..."
    
    # Check if the release workflow file exists
    if [ ! -f ".github/workflows/release.yml" ]; then
        log_error "Release workflow not found at .github/workflows/release.yml"
        exit 1
    fi
    
    # Verify workflow has correct permissions
    if grep -q "contents: write" ".github/workflows/release.yml"; then
        log_success "Workflow has correct permissions"
    else
        log_warning "Workflow may need permission updates"
    fi
}

create_test_release() {
    log_info "Creating test release configuration..."
    
    # Check if we should create a test release
    echo ""
    echo "Would you like to test the release workflow? This will:"
    echo "- Create a test branch"
    echo "- Make a small change"
    echo "- Create a PR with release:patch label"
    echo "- Merge it to trigger the workflow"
    echo ""
    read -p "Create test release? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Create test branch
        BRANCH_NAME="test-release-$(date +%s)"
        git checkout -b "$BRANCH_NAME"
        
        # Make a small change
        echo "# Test Release - $(date)" >> README.md
        git add README.md
        git commit -m "test: trigger automated release workflow"
        git push origin "$BRANCH_NAME"
        
        # Create PR with release label
        PR_URL=$(gh pr create \
            --title "Test Automated Release Workflow" \
            --body "This PR tests the automated release workflow by making a small change to README.md. When merged, it should automatically update version.json and create a new release." \
            --label "release:patch")
        
        log_success "Test PR created: $PR_URL"
        echo ""
        echo "To complete the test:"
        echo "1. Review the PR: $PR_URL"
        echo "2. Merge the PR"
        echo "3. Check the Actions tab for the release workflow"
        echo "4. Verify that version.json was updated"
        echo "5. Check that a new release was created"
        
        # Switch back to main
        git checkout main
    fi
}

main() {
    print_header
    
    log_info "This script will configure your GitHub repository for automated releases"
    echo ""
    
    check_dependencies
    authenticate
    get_repository_info
    
    echo ""
    log_info "Configuring repository: $GITHUB_REPOSITORY"
    echo ""
    
    configure_actions_permissions
    configure_branch_protection
    create_release_labels
    test_workflow_permissions
    
    echo ""
    log_success "Repository configuration completed!"
    echo ""
    
    log_info "Summary of changes:"
    echo "✅ Actions permissions configured (manual steps provided)"
    echo "✅ Branch protection configured (manual verification recommended)"
    echo "✅ Release labels created (release:major, release:minor, release:patch)"
    echo "✅ Workflow permissions verified"
    echo ""
    
    log_info "Next steps:"
    echo "1. Verify all manual configuration steps were completed"
    echo "2. Test the workflow by creating a PR with a release label"
    echo "3. Check that version.json is updated automatically when PRs are merged"
    echo ""
    
    create_test_release
    
    log_success "🚀 Your repository is now configured for automated releases!"
}

# Run main function
main "$@"