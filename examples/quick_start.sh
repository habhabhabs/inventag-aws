#!/bin/bash

# InvenTag Quick Start Script
# This script helps you get started with InvenTag BOM generation quickly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        print_error "Python is not installed. Please install Python 3.7 or later."
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
        print_error "Python 3.7 or later is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION found"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        $PYTHON_CMD -m pip install -r requirements.txt
        print_success "Dependencies installed successfully"
    else
        print_warning "requirements.txt not found. Installing basic dependencies..."
        $PYTHON_CMD -m pip install boto3 openpyxl python-docx pyyaml
    fi
}

# Function to check AWS credentials
check_aws_credentials() {
    print_status "Checking AWS credentials..."
    
    if command_exists aws; then
        if aws sts get-caller-identity >/dev/null 2>&1; then
            ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
            print_success "AWS credentials are valid"
            print_status "Account ID: $ACCOUNT_ID"
            print_status "User/Role: $USER_ARN"
            return 0
        else
            print_warning "AWS credentials are not configured or invalid"
            return 1
        fi
    else
        print_warning "AWS CLI is not installed"
        return 1
    fi
}

# Function to create sample configuration
create_sample_config() {
    print_status "Creating sample configuration files..."
    
    # Create config directory
    mkdir -p config
    
    # Create sample accounts configuration
    if [ ! -f "config/accounts.json" ]; then
        cat > config/accounts.json << 'EOF'
{
  "accounts": [
    {
      "account_id": "123456789012",
      "account_name": "My AWS Account",
      "profile_name": "default",
      "regions": ["us-east-1"],
      "services": [],
      "tags": {}
    }
  ],
  "settings": {
    "max_concurrent_accounts": 1,
    "account_processing_timeout": 1800,
    "output_directory": "bom_output"
  }
}
EOF
        print_success "Created config/accounts.json"
    else
        print_status "config/accounts.json already exists"
    fi
    
    # Create sample service descriptions
    if [ ! -f "config/service_descriptions.yaml" ]; then
        cat > config/service_descriptions.yaml << 'EOF'
EC2:
  default_description: "Amazon Elastic Compute Cloud - Virtual servers in the cloud"
  resource_types:
    Instance: "Virtual machine instances providing scalable compute capacity"
    Volume: "Block storage volumes attached to EC2 instances"
    SecurityGroup: "Virtual firewall controlling traffic to instances"

S3:
  default_description: "Amazon Simple Storage Service - Object storage service"
  resource_types:
    Bucket: "Container for objects stored in Amazon S3"

RDS:
  default_description: "Amazon Relational Database Service - Managed database service"
  resource_types:
    DBInstance: "Managed database instance with automated backups"
EOF
        print_success "Created config/service_descriptions.yaml"
    else
        print_status "config/service_descriptions.yaml already exists"
    fi
    
    # Create sample tag mappings
    if [ ! -f "config/tag_mappings.yaml" ]; then
        cat > config/tag_mappings.yaml << 'EOF'
"Environment":
  column_name: "Environment"
  default_value: "Unknown"
  description: "Environment classification (prod, staging, dev)"

"Owner":
  column_name: "Resource Owner"
  default_value: "Unassigned"
  description: "Person or team responsible for the resource"

"Project":
  column_name: "Project"
  default_value: ""
  description: "Project or application the resource belongs to"
EOF
        print_success "Created config/tag_mappings.yaml"
    else
        print_status "config/tag_mappings.yaml already exists"
    fi
}

# Function to run basic validation
run_validation() {
    print_status "Running configuration validation..."
    
    if $PYTHON_CMD inventag_cli.py --accounts-file config/accounts.json --validate-config; then
        print_success "Configuration validation passed"
    else
        print_error "Configuration validation failed"
        return 1
    fi
    
    if check_aws_credentials; then
        print_status "Running credential validation..."
        if $PYTHON_CMD inventag_cli.py --accounts-file config/accounts.json --validate-credentials; then
            print_success "Credential validation passed"
        else
            print_error "Credential validation failed"
            return 1
        fi
    else
        print_warning "Skipping credential validation (AWS credentials not configured)"
    fi
}

# Function to run sample BOM generation
run_sample_bom() {
    print_status "Generating sample BOM report..."
    
    # Create output directory
    mkdir -p bom_output
    
    # Run BOM generation
    if $PYTHON_CMD inventag_cli.py \
        --accounts-file config/accounts.json \
        --service-descriptions config/service_descriptions.yaml \
        --tag-mappings config/tag_mappings.yaml \
        --create-excel \
        --verbose; then
        
        print_success "BOM generation completed successfully!"
        
        # List generated files
        if [ -d "bom_output" ] && [ "$(ls -A bom_output)" ]; then
            print_status "Generated files:"
            for file in bom_output/*; do
                if [ -f "$file" ]; then
                    echo "  - $(basename "$file")"
                fi
            done
        fi
    else
        print_error "BOM generation failed"
        return 1
    fi
}

# Function to show next steps
show_next_steps() {
    print_success "InvenTag setup completed successfully!"
    echo
    print_status "Next steps:"
    echo "1. Review and customize the configuration files in the config/ directory"
    echo "2. Update config/accounts.json with your actual AWS account details"
    echo "3. Customize service descriptions and tag mappings as needed"
    echo "4. Run BOM generation with different options:"
    echo
    echo "   # Generate Excel and Word reports"
    echo "   $PYTHON_CMD inventag_cli.py --create-excel --create-word"
    echo
    echo "   # Generate with custom configuration"
    echo "   $PYTHON_CMD inventag_cli.py \\"
    echo "     --accounts-file config/accounts.json \\"
    echo "     --service-descriptions config/service_descriptions.yaml \\"
    echo "     --tag-mappings config/tag_mappings.yaml \\"
    echo "     --create-excel --verbose"
    echo
    echo "   # Multi-account setup"
    echo "   $PYTHON_CMD inventag_cli.py --accounts-prompt --create-excel"
    echo
    echo "5. For help and more options:"
    echo "   $PYTHON_CMD inventag_cli.py --help"
    echo
    print_status "Documentation available in the docs/ directory"
}

# Function to show usage
show_usage() {
    echo "InvenTag Quick Start Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --skip-deps     Skip dependency installation"
    echo "  --skip-config   Skip configuration file creation"
    echo "  --skip-validate Skip validation steps"
    echo "  --skip-bom      Skip sample BOM generation"
    echo "  --help          Show this help message"
    echo
    echo "This script will:"
    echo "1. Check Python version and install dependencies"
    echo "2. Check AWS credentials"
    echo "3. Create sample configuration files"
    echo "4. Validate configuration and credentials"
    echo "5. Generate a sample BOM report"
}

# Main execution
main() {
    local skip_deps=false
    local skip_config=false
    local skip_validate=false
    local skip_bom=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-deps)
                skip_deps=true
                shift
                ;;
            --skip-config)
                skip_config=true
                shift
                ;;
            --skip-validate)
                skip_validate=true
                shift
                ;;
            --skip-bom)
                skip_bom=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    echo "========================================="
    echo "       InvenTag Quick Start Script      "
    echo "========================================="
    echo
    
    # Step 1: Check Python version
    print_status "Step 1: Checking Python version..."
    check_python_version
    echo
    
    # Step 2: Install dependencies
    if [ "$skip_deps" = false ]; then
        print_status "Step 2: Installing dependencies..."
        install_dependencies
        echo
    else
        print_warning "Step 2: Skipping dependency installation"
        echo
    fi
    
    # Step 3: Check AWS credentials
    print_status "Step 3: Checking AWS credentials..."
    check_aws_credentials
    echo
    
    # Step 4: Create sample configuration
    if [ "$skip_config" = false ]; then
        print_status "Step 4: Creating sample configuration..."
        create_sample_config
        echo
    else
        print_warning "Step 4: Skipping configuration file creation"
        echo
    fi
    
    # Step 5: Run validation
    if [ "$skip_validate" = false ]; then
        print_status "Step 5: Running validation..."
        if run_validation; then
            echo
        else
            print_error "Validation failed. Please check your configuration and credentials."
            exit 1
        fi
    else
        print_warning "Step 5: Skipping validation"
        echo
    fi
    
    # Step 6: Generate sample BOM
    if [ "$skip_bom" = false ]; then
        print_status "Step 6: Generating sample BOM..."
        if run_sample_bom; then
            echo
        else
            print_error "BOM generation failed. Please check the logs for details."
            exit 1
        fi
    else
        print_warning "Step 6: Skipping sample BOM generation"
        echo
    fi
    
    # Show next steps
    show_next_steps
}

# Run main function with all arguments
main "$@"