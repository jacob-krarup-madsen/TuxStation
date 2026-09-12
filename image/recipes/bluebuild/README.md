# Custom Atomic Linux Distribution (BlueBuild)

Welcome to your custom atomic Linux distribution project repository built with **BlueBuild** and **Fedora Atomic / bootc**.

## 🚀 How It Works
1. **Declare Configuration**: Customize packages, desktop settings, flatpaks, and services in [`config/recipe.yml`](config/recipe.yml).
2. **Automated CI/CD**: Pushing to `main` triggers GitHub Actions to build an OCI container image and push it to GitHub Container Registry (`ghcr.io`).
3. **Deploy & Rebase**: Rebase any Fedora Silverblue or Fedora Atomic installation onto your container image.

---

## 📦 How to Rebase an Existing Fedora Atomic Host

Run the following command on your target Linux machine (replace `your-username` with your GitHub username):

### Using `bootc` (Modern Container OS):
```bash
sudo bootc switch ghcr.io/your-username/custom-atomic-os:latest
```

### Using `rpm-ostree`:
```bash
sudo rpm-ostree rebase ostree-unverified-registry:ghcr.io/your-username/custom-atomic-os:latest
```

Then reboot:
```bash
sudo reboot
```

---

## 🛠️ Modules Available in `recipe.yml`
- **`rpm-ostree`**: Layer RPM packages or remove base RPMs.
- **`default-flatpaks`**: Pre-install system-wide Flatpak applications.
- **`systemd`**: Enable/disable system services.
- **`files`**: Copy files into `/usr` or `/etc`.
- **`gnome-extensions`**: Pre-configure desktop extensions.
