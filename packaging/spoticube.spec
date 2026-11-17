%global pysitelib %(python3 -c "import sysconfig; print(sysconfig.get_path('purelib', vars={'base':'/usr','platbase':'/usr'}))")

Name:           spoticube
Version:        0.1.0
Release:        1%{?dist}
Summary:        Графический загрузчик видео и аудио с YouTube
License:        MIT
URL:            https://github.com/barsuk228332/spoticube
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3
Requires:       python3-pyside6
Requires:       yt-dlp
Requires:       hicolor-icon-theme
Recommends:     ffmpeg

%description
Spoticube — приложение на PySide6 для поиска и скачивания видео и аудио
с YouTube. Поиск идёт через yt-dlp без API-ключей, результаты показываются
сеткой карточек с превью, справа — панель предпросмотра. Загрузки идут
очередью с прогрессом, скоростью, ETA и отменой; поддерживаются MP4
с выбором качества и MP3 с выбором битрейта.

Для конвертации в MP3 и склейки видео нужен ffmpeg (пакет Recommends).

%prep
%autosetup -n %{name}-%{version}

%build
%{__python3} -m compileall -q -f main.py %{name}

%install
install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} <<'EOF'
#!%{__python3}
"""Запуск Spoticube из системной установки."""

import sys

from spoticube.app import main

raise SystemExit(main())
EOF
chmod 0755 %{buildroot}%{_bindir}/%{name}

install -d %{buildroot}%{pysitelib}/%{name}
cp -r %{name}/. %{buildroot}%{pysitelib}/%{name}/
find %{buildroot}%{pysitelib}/%{name} -name '__pycache__' -type d -prune -exec rm -rf {} +

install -d %{buildroot}%{_datadir}/%{name}
cp -r assets %{buildroot}%{_datadir}/%{name}/

install -Dpm644 packaging/%{name}.desktop %{buildroot}%{_datadir}/applications/%{name}.desktop
install -Dpm644 assets/%{name}.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

for png in assets/icons/%{name}-*.png; do
    size=${png##*-}
    size=${size%.png}
    [ "$size" = 1024 ] && continue
    install -Dpm644 "$png" "%{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/%{name}.png"
done

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{pysitelib}/%{name}
%{_datadir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.png
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%changelog
* Tue Nov 17 2026 barsuk <barsuk@localhost> - 0.1.0-1
- Первая сборка пакета
