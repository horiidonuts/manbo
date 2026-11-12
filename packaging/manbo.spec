Name:           manbo
Version:        0.1.0
Release:        5%{?dist}
Summary:        A tiny pastel Pomodoro timer
License:        MIT
URL:            https://github.com/horiidonuts/manbo
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  desktop-file-utils
Requires:       python3
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk4
Requires:       libadwaita
Requires:       gstreamer1
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good
Recommends:     sound-theme-freedesktop

%global app_id io.github.horiidonuts.Manbo

%description
Manbo is a small Pomodoro timer with pastel themes and a big, squishy
3D start button. Focus, short break, long break and the long break
interval are all configurable.

%prep
%autosetup

%build
# nothing to build

%install
install -Dm755 bin/manbo %{buildroot}%{_bindir}/manbo
install -d %{buildroot}%{_datadir}/manbo/manbo
install -m644 manbo/*.py %{buildroot}%{_datadir}/manbo/manbo/
install -d %{buildroot}%{_datadir}/manbo/data
cp -a data/sounds %{buildroot}%{_datadir}/manbo/data/
install -Dm644 data/%{app_id}.desktop %{buildroot}%{_datadir}/applications/%{app_id}.desktop
install -Dm644 data/icons/hicolor/scalable/apps/%{app_id}.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{app_id}.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{app_id}.desktop

%files
%license LICENSE
%doc README.md
%{_bindir}/manbo
%{_datadir}/manbo/
%{_datadir}/applications/%{app_id}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{app_id}.svg

%changelog
* Thu Nov 12 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-5
- Fix clicks starting softened: play effects without clock sync

* Thu Nov 12 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-4
- Keep the audio device awake while focused and around session end so
  sounds don't lose their start after a few seconds of silence

* Thu Nov 12 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-3
- Fix clicks dropping out when the button is pressed quickly
- Recover sound playback after the audio server restarts

* Thu Nov 12 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-2
- Fix button sounds playing only once

* Thu Nov 12 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-1
- Initial release
