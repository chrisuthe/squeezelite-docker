#!/bin/bash

# Squeezelite Multi-Room Docker Management Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
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

# Check if docker and docker-compose are available
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    print_success "Docker and Docker Compose are available"
}

# Create necessary directories
setup_directories() {
    print_status "Creating necessary directories..."
    mkdir -p config logs
    print_success "Directories created"
}

# Check audio devices
check_audio() {
    print_status "Checking audio devices on host..."
    
    if [ ! -d "/dev/snd" ]; then
        print_warning "No /dev/snd directory found. Audio devices may not be available."
        return
    fi
    
    print_status "Available audio devices:"
    if command -v aplay &> /dev/null; then
        aplay -l 2>/dev/null || print_warning "Could not list audio devices"
    else
        print_warning "aplay command not found. Install alsa-utils to check audio devices."
    fi
    
    print_status "Audio device permissions:"
    ls -la /dev/snd/ 2>/dev/null || print_warning "Could not check /dev/snd permissions"
}

# Build the Docker image
build() {
    print_status "Building Squeezelite Multi-Room Docker image..."
    docker-compose build
    print_success "Build completed"
}

# Start the services
start() {
    print_status "Starting Squeezelite Multi-Room services..."
    docker-compose up -d
    print_success "Services started"
    
    # Wait a moment for services to initialize
    sleep 3
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        print_success "Services are running successfully"
        print_status "Web interface available at: http://localhost:8080"
    else
        print_error "Services failed to start. Check logs with: $0 logs"
        exit 1
    fi
}

# Stop the services
stop() {
    print_status "Stopping Squeezelite Multi-Room services..."
    docker-compose down
    print_success "Services stopped"
}

# Restart the services
restart() {
    print_status "Restarting Squeezelite Multi-Room services..."
    stop
    start
}

# Show logs
logs() {
    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

# Show status
status() {
    print_status "Service status:"
    docker-compose ps
    
    print_status "Player logs:"
    if [ -d "logs" ]; then
        ls -la logs/
    else
        print_warning "No logs directory found"
    fi
}

# Clean up
clean() {
    print_warning "This will remove all containers, images, and data. Are you sure? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Cleaning up..."
        docker-compose down -v --rmi all
        docker system prune -f
        print_success "Cleanup completed"
    else
        print_status "Cleanup cancelled"
    fi
}

# Development mode
dev() {
    print_status "Starting in development mode..."
    export COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml
    docker-compose up --build
}

# Start services in no-audio mode
start_no_audio() {
    print_status "Starting Squeezelite Multi-Room services (no audio devices)..."
    check_dependencies
    setup_directories
    
    print_status "Using no-audio configuration - virtual/null devices only"
    export COMPOSE_FILE="docker-compose.no-audio.yml"
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        print_success "Services started successfully in no-audio mode"
        
        # Wait for services to initialize
        sleep 3
        
        print_success "Services are running in no-audio mode"
        print_status "Web interface available at: http://localhost:8080"
        print_status "Note: Only virtual audio devices (null, default) will be available"
    else
        print_error "Failed to start services in no-audio mode"
        exit 1
    fi
}

# Debug container issues
debug() {
    print_status "Running container diagnostics..."
    
    if [ -f "debug.sh" ]; then
        chmod +x debug.sh
        ./debug.sh
    else
        print_error "debug.sh script not found"
        
        # Basic debugging without the script
        print_status "Running basic diagnostics..."
        
        echo "Container status:"
        docker-compose ps
        
        echo -e "\nRecent logs:"
        docker-compose logs --tail=20 squeezelite-multiroom
        
        echo -e "\nFor more detailed debugging, ensure debug.sh exists"
    fi
}

# Update
update() {
    print_status "Updating Squeezelite Multi-Room..."
    git pull 2>/dev/null || print_warning "Git pull failed or not a git repository"
    build
    restart
    print_success "Update completed"
}

# Show help
show_help() {
    echo "Squeezelite Multi-Room Docker Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build     Build the Docker image"
    echo "  start     Start the services"
    echo "  stop      Stop the services"
    echo "  restart   Restart the services"
    echo "  status    Show service status"
    echo "  logs      Show logs (optionally specify service name)"
    echo "  clean     Clean up all containers and images"
    echo "  dev       Start in development mode"
    echo "  no-audio  Start without audio devices (testing/dev)"
    echo "  debug     Run container diagnostics"
    echo "  update    Update and restart services"
    echo "  setup     Initial setup and checks"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start all services"
    echo "  $0 logs squeezelite-web     # Show web service logs"
    echo "  $0 restart                  # Restart all services"
}

# Main script logic
main() {
    case "${1:-help}" in
        build)
            check_dependencies
            setup_directories
            build
            ;;
        start)
            check_dependencies
            setup_directories
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        logs)
            logs "$2"
            ;;
        clean)
            clean
            ;;
        dev)
            check_dependencies
            setup_directories
            dev
            ;;
        no-audio)
            start_no_audio
            ;;
        debug)
            debug
            ;;
        update)
            update
            ;;
        setup)
            check_dependencies
            setup_directories
            check_audio
            print_success "Setup completed. Run '$0 build' to build the image."
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
