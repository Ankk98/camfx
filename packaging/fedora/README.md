# Fedora Packaging Quick Commands (v0.2.0a1)

From repo root:

```bash
rm -rf dist build *.egg-info
python -m build
rpmdev-setuptree
cp dist/camfx-0.2.0a1.tar.gz ~/rpmbuild/SOURCES/
rpmbuild -ba packaging/fedora/camfx.spec
ls -lh ~/rpmbuild/RPMS/*/camfx-0.2.0a1-*.rpm
```

Install and run:

```bash
sudo dnf install -y ~/rpmbuild/RPMS/*/camfx-0.2.0a1-*.rpm
sudo dnf install -y v4l2loopback akmod-v4l2loopback v4l-utils
sudo modprobe v4l2loopback exclusive_caps=1 card_label="camfx" video_nr=-1
systemctl --user daemon-reload
systemctl --user enable --now camfx
systemctl --user status camfx --no-pager
```
