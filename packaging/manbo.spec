Name:           manbo
Version:        0.1.0
Release:        15%{?dist}
Summary:        A tiny pastel Pomodoro timer
License:        MIT AND LicenseRef-Splice-Sounds
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
# the Plasma widget (plasma/) talks to the app through this QML module
Recommends:     plasma-workspace

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
sh packaging/install.sh %{buildroot}

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{app_id}.desktop

%files
%license LICENSE NOTICE
%doc README.md
%{_bindir}/manbo
%{_datadir}/manbo/
%{_datadir}/applications/%{app_id}.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{app_id}.svg
%{_datadir}/dbus-1/services/%{app_id}.service
%{_datadir}/plasma/plasmoids/io.github.horiidonuts.manbo/

%changelog
* Sun Nov 15 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-15
- When a session ends the button pops first, then half a second later the
  app moves on to the next session
- Ship only the sounds in use, with a NOTICE about their license

* Sun Nov 15 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-14
- Plasma widget: a small timer on the panel, a little Manbo on the desktop
- D-Bus: GetState/StateChanged (JSON), Palette/CyclePosition/LongBreakInterval,
  D-Bus activation so the widget can start Manbo

* Sun Nov 15 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-13
- D-Bus API for widgets and scripts
- Optional Do Not Disturb while focusing
- Optional: keep running in the background when closed

* Sun Nov 15 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-12
- Mini mode: a small always-on-top pill (Ctrl+M)

* Sun Nov 15 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-11
- Optional: bring the window to the front a second before a session ends
- Rolling digit animation for the clock (optional, on by default)

* Fri Nov 13 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-9
- Play a tab sound when switching modes by hand
- New button press and pop sounds

* Fri Nov 13 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.1.0-6
- Send the session-finished notification as urgent so it gets through
  Do Not Disturb; withdraw it when the window is focused again

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
