# TuxStation Master Command Runner

# Default recipe: display available workflows
default:
    @just --list

# Build the custom Fedora Atomic / bootc container image
build-image:
    podman build -t tuxstation:latest -f image/Containerfile image/

# Run the Tuxility system maintenance assistant
maintain:
    python3 tools/tuxility/tuxility

# Apply dotfiles, GNOME configurations, and flatpaks
dotfiles:
    python3 dotfiles/distroconfig/app.py

# Check status of system and container recipes
status:
    @echo "=== TuxStation Status ==="
    @echo "Image definitions: image/"
    @echo "Maintenance tools: tools/tuxility/"
    @echo "User dotfiles:     dotfiles/distroconfig/"
