%global debug_package %{nil}

Name:           camfx
Version:        0.2.0a1
Release:        1%{?dist}
Summary:        Camera effects middleware with virtual camera output

License:        MIT
URL:            https://github.com/ankk98/camfx
Source0:        %{name}-0.2.0a1.tar.gz

BuildArch:      x86_64
AutoReqProv:    no

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  systemd-rpm-macros

Requires:       ffmpeg
Requires:       python3
Requires:       gtk4
Requires:       python3-gobject

%description
camfx is a Linux camera effects middleware that processes a physical camera
feed and publishes output to a virtual V4L2 device for video conferencing apps.

This alpha package includes the CLI, core daemon, and a systemd user unit.

%prep
%autosetup -n %{name}-0.2.0a1

%build
%py3_build

%install
%py3_install

install -Dpm0644 packaging/fedora/camfx.service \
  %{buildroot}%{_userunitdir}/camfx.service
install -Dpm0644 packaging/fedora/camfx.desktop \
  %{buildroot}%{_datadir}/applications/camfx.desktop

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/camfx/
%{python3_sitelib}/camfx-*.egg-info/
%{_bindir}/camfx
%{_userunitdir}/camfx.service
%{_datadir}/applications/camfx.desktop

%changelog
* Thu Mar 26 2026 camfx maintainers - 0.2.0a1-1
- Initial Fedora alpha package for GitHub manual release flow.
