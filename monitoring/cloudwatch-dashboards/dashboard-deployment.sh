#!/bin/bash

# CloudWatch Dashboard Deployment Script
# This script deploys all Flight Data Pipeline dashboards to AWS CloudWatch

set -e

# Configuration
REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT=${ENVIRONMENT:-prod}
DASHBOARD_PREFIX="FlightData"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Check if dashboard files exist
    local dashboard_files=(
        "executive-dashboard.json"
        "technical-dashboard.json" 
        "data-quality-dashboard.json"
    )
    
    for file in "${dashboard_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Dashboard file $file not found!"
            exit 1
        fi
    done
    
    log_success "Prerequisites check passed"
}

# Function to validate JSON files
validate_json() {
    local file=$1
    log_info "Validating JSON syntax for $file..."
    
    if python3 -m json.tool "$file" > /dev/null 2>&1; then
        log_success "JSON validation passed for $file"
        return 0
    else
        log_error "JSON validation failed for $file"
        return 1
    fi
}

# Function to update dashboard for specific environment
update_dashboard_environment() {
    local file=$1
    local environment=$2
    local temp_file="${file%.json}-${environment}.json"
    
    log_info "Creating environment-specific dashboard for $environment..."
    
    # Replace environment-specific values
    sed "s/-prod/-${environment}/g" "$file" > "$temp_file"
    
    # Update dashboard title
    sed -i "s/\"title\": \"\(.*\)\"/\"title\": \"\1 (${environment^^})\"/g" "$temp_file"
    
    echo "$temp_file"
}

# Function to deploy a single dashboard
deploy_dashboard() {
    local file=$1
    local dashboard_name=$2
    local environment=$3
    
    log_info "Deploying dashboard: $dashboard_name"
    
    # Validate JSON first
    if ! validate_json "$file"; then
        return 1
    fi
    
    # Create environment-specific version if not prod
    local deploy_file="$file"
    if [[ "$environment" != "prod" ]]; then
        deploy_file=$(update_dashboard_environment "$file" "$environment")
    fi
    
    # Deploy the dashboard
    if aws cloudwatch put-dashboard \
        --region "$REGION" \
        --dashboard-name "${dashboard_name}-${environment^^}" \
        --dashboard-body "file://$deploy_file"; then
        
        log_success "Successfully deployed $dashboard_name for $environment"
        
        # Clean up temporary file
        if [[ "$deploy_file" != "$file" ]]; then
            rm -f "$deploy_file"
        fi
        
        return 0
    else
        log_error "Failed to deploy $dashboard_name for $environment"
        
        # Clean up temporary file on failure
        if [[ "$deploy_file" != "$file" ]]; then
            rm -f "$deploy_file"
        fi
        
        return 1
    fi
}

# Function to create dashboard URLs
create_dashboard_urls() {
    local environment=$1
    
    cat << EOF

🔗 Dashboard URLs (Region: $REGION, Environment: ${environment^^}):

Executive Dashboard:
https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_PREFIX}-Executive-${environment^^}

Technical Dashboard:
https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_PREFIX}-Technical-${environment^^}

Data Quality Dashboard:
https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${DASHBOARD_PREFIX}-DataQuality-${environment^^}

EOF
}

# Function to verify deployment
verify_deployment() {
    local environment=$1
    local dashboards=(
        "${DASHBOARD_PREFIX}-Executive-${environment^^}"
        "${DASHBOARD_PREFIX}-Technical-${environment^^}"
        "${DASHBOARD_PREFIX}-DataQuality-${environment^^}"
    )
    
    log_info "Verifying dashboard deployment..."
    
    for dashboard in "${dashboards[@]}"; do
        if aws cloudwatch get-dashboard \
            --region "$REGION" \
            --dashboard-name "$dashboard" &> /dev/null; then
            log_success "✓ $dashboard is accessible"
        else
            log_error "✗ $dashboard is not accessible"
            return 1
        fi
    done
    
    log_success "All dashboards verified successfully"
    return 0
}

# Function to list existing dashboards
list_dashboards() {
    log_info "Existing Flight Data dashboards:"
    
    aws cloudwatch list-dashboards \
        --region "$REGION" \
        --query "DashboardEntries[?starts_with(DashboardName, '${DASHBOARD_PREFIX}')].{Name:DashboardName,LastModified:LastModified}" \
        --output table
}

# Function to delete dashboards (for cleanup)
delete_dashboards() {
    local environment=$1
    local dashboards=(
        "${DASHBOARD_PREFIX}-Executive-${environment^^}"
        "${DASHBOARD_PREFIX}-Technical-${environment^^}"
        "${DASHBOARD_PREFIX}-DataQuality-${environment^^}"
    )
    
    log_warning "Deleting dashboards for environment: $environment"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for dashboard in "${dashboards[@]}"; do
            if aws cloudwatch delete-dashboard \
                --region "$REGION" \
                --dashboard-name "$dashboard" &> /dev/null; then
                log_success "Deleted $dashboard"
            else
                log_warning "Dashboard $dashboard not found or already deleted"
            fi
        done
    else
        log_info "Deletion cancelled"
    fi
}

# Function to backup existing dashboards
backup_dashboards() {
    local environment=$1
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    local dashboards=(
        "${DASHBOARD_PREFIX}-Executive-${environment^^}"
        "${DASHBOARD_PREFIX}-Technical-${environment^^}"
        "${DASHBOARD_PREFIX}-DataQuality-${environment^^}"
    )
    
    log_info "Backing up existing dashboards to $backup_dir..."
    mkdir -p "$backup_dir"
    
    for dashboard in "${dashboards[@]}"; do
        if aws cloudwatch get-dashboard \
            --region "$REGION" \
            --dashboard-name "$dashboard" \
            --query "DashboardBody" \
            --output text > "$backup_dir/${dashboard}.json" 2>/dev/null; then
            log_success "Backed up $dashboard"
        else
            log_warning "Could not backup $dashboard (may not exist)"
        fi
    done
}

# Function to show help
show_help() {
    cat << EOF
CloudWatch Dashboard Deployment Script

Usage: $0 [OPTIONS] COMMAND

Commands:
    deploy      Deploy dashboards to CloudWatch
    list        List existing Flight Data dashboards
    delete      Delete dashboards from CloudWatch
    backup      Backup existing dashboards
    verify      Verify deployed dashboards
    help        Show this help message

Options:
    -r, --region REGION       AWS region (default: us-east-1)
    -e, --environment ENV     Environment (default: prod)
    -h, --help               Show this help message

Environment Variables:
    AWS_REGION               AWS region to deploy to
    ENVIRONMENT             Target environment (dev, staging, prod)
    AWS_PROFILE             AWS profile to use

Examples:
    # Deploy to production
    $0 deploy

    # Deploy to staging environment
    $0 -e staging deploy
    
    # Deploy to different region
    $0 -r eu-west-1 deploy
    
    # List existing dashboards
    $0 list
    
    # Backup before deployment
    $0 backup && $0 deploy
    
    # Delete staging dashboards
    $0 -e staging delete

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        deploy|list|delete|backup|verify|help)
            COMMAND="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Default command
COMMAND=${COMMAND:-deploy}

# Main execution
main() {
    log_info "Flight Data Pipeline Dashboard Deployment"
    log_info "Region: $REGION, Environment: $ENVIRONMENT, Command: $COMMAND"
    echo
    
    case $COMMAND in
        deploy)
            check_prerequisites
            backup_dashboards "$ENVIRONMENT"
            
            # Deploy dashboards
            local success=true
            
            if ! deploy_dashboard "executive-dashboard.json" "${DASHBOARD_PREFIX}-Executive" "$ENVIRONMENT"; then
                success=false
            fi
            
            if ! deploy_dashboard "technical-dashboard.json" "${DASHBOARD_PREFIX}-Technical" "$ENVIRONMENT"; then
                success=false
            fi
            
            if ! deploy_dashboard "data-quality-dashboard.json" "${DASHBOARD_PREFIX}-DataQuality" "$ENVIRONMENT"; then
                success=false
            fi
            
            if $success; then
                log_success "All dashboards deployed successfully!"
                verify_deployment "$ENVIRONMENT"
                create_dashboard_urls "$ENVIRONMENT"
            else
                log_error "Some dashboards failed to deploy"
                exit 1
            fi
            ;;
        list)
            list_dashboards
            ;;
        delete)
            delete_dashboards "$ENVIRONMENT"
            ;;
        backup)
            backup_dashboards "$ENVIRONMENT"
            ;;
        verify)
            verify_deployment "$ENVIRONMENT"
            create_dashboard_urls "$ENVIRONMENT"
            ;;
        help)
            show_help
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"