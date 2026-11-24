Name:           manbo
Version:        0.7.1
Release:        1%{?dist}
Summary:        A tiny pastel Pomodoro timer
License:        MIT AND LicenseRef-Splice-Sounds
URL:            https://github.com/horiidonuts/manbo
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  desktop-file-utils
Requires:       python3
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       python3-qrcode
Requires:       gtk4
Requires:       libadwaita
Requires:       gstreamer1
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good
Recommends:     sound-theme-freedesktop
# the Plasma widget (plasma/) talks to the app through this QML module
Recommends:     plasma-workspace
# ...and on GNOME there's a top bar extension (gnome/)
Suggests:       gnome-shell

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
%{_datadir}/gnome-shell/extensions/manbo@horiidonuts.github.io/

%changelog
* Tue Nov 24 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.7.1-1
- Cheerful messages: session-end notifications, the empty sky, phone sync
  and pairing, the widget and top bar while Manbo is closed

* Tue Nov 24 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.7.0-1
- Turkish: Preferences → Language (System / English / Türkçe), also in the
  Plasma widget and the GNOME top bar
- Phone sync finds the PC again after its address changes, on any network or
  the phone's hotspot, without pairing again

* Tue Nov 24 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.6.1-1
- Stars panel: a full-bleed twilight sky, from a pale horizon glow with
  clouds down to deep night, scrolling with the stats

* Thu Nov 19 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.6.0-1
- Stars: every finished focus session lights a star; a week of night sky with
  a constellation per day, plus today, streak, week and all-time stats
- Stars sync with the phone

* Tue Nov 17 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.5.0-2
- Four new themes: Frosty, Periwinkle, Golden Summer and Autumn
- New logo and app icon

* Mon Nov 16 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.4.0-1
- Phone sync: pair Manbo for Android with a QR code (Preferences -> Phone)
  and the timer, its lengths and Do Not Disturb stay in step on both

* Sun Nov 15 2026 horiidonuts <horiidonuts@users.noreply.github.com> - 0.2.0-1
- GNOME Shell extension: the timer in the top bar, with start/pause, reset,
  modes and "Open Manbo" (GNOME 45-50)
- Exit with a clear message when there's no display instead of crashing

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
