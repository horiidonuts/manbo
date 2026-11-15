NAME    := manbo
VERSION := $(shell sed -n 's/^Version:[[:space:]]*//p' packaging/manbo.spec)
TOPDIR  := $(CURDIR)/build/rpm
TARBALL := $(TOPDIR)/SOURCES/$(NAME)-$(VERSION).tar.gz

WIDGET  := plasma/io.github.horiidonuts.manbo

.PHONY: run stage tarball rpm deb clean widget-install widget-remove

run:
	python3 -m manbo

# install / update the Plasma widget for this user only (no RPM needed)
widget-install:
	kpackagetool6 -t Plasma/Applet -u $(WIDGET) 2>/dev/null || kpackagetool6 -t Plasma/Applet -i $(WIDGET)

widget-remove:
	kpackagetool6 -t Plasma/Applet -r io.github.horiidonuts.manbo

RELEASE := $(shell sed -n 's/^Release:[[:space:]]*\([0-9]*\).*/\1/p' packaging/manbo.spec)
STAGE   := $(CURDIR)/build/stage/$(NAME)-$(VERSION)
# only the sound files the app uses (see packaging/used-sounds.py and NOTICE)
SOUND_FILES = $(shell python3 packaging/used-sounds.py)

# source tree for packaging: code, data, and just the sounds in use
stage:
	rm -rf $(STAGE) && mkdir -p $(STAGE)/data/sounds
	cp -a bin manbo plasma packaging Makefile README.md LICENSE NOTICE $(STAGE)/
	cp -a data/*.desktop data/*.service data/icons $(STAGE)/data/
	cp -a data/sounds/README.md $(SOUND_FILES) $(STAGE)/data/sounds/
	find $(STAGE) -name __pycache__ -prune -exec rm -rf {} +

tarball: stage
	mkdir -p $(TOPDIR)/SOURCES
	tar -C $(dir $(STAGE)) -czf $(TARBALL) $(NAME)-$(VERSION)

DEBROOT := $(CURDIR)/build/deb/root
DEB     := $(CURDIR)/build/$(NAME)_$(VERSION)-$(RELEASE)_all.deb

deb: stage
	rm -rf $(DEBROOT) && mkdir -p $(DEBROOT)/DEBIAN $(DEBROOT)/usr/share/doc/$(NAME)
	cd $(STAGE) && sh packaging/install.sh $(DEBROOT)
	cp README.md LICENSE NOTICE packaging/debian/copyright $(DEBROOT)/usr/share/doc/$(NAME)/
	sed -e 's/@VERSION@/$(VERSION)-$(RELEASE)/' \
	    -e "s/@SIZE@/$$(du -sk $(DEBROOT)/usr | cut -f1)/" \
	    packaging/debian/control.in > $(DEBROOT)/DEBIAN/control
	dpkg-deb --build --root-owner-group $(DEBROOT) $(DEB)

rpm: tarball
	rpmbuild --define "_topdir $(TOPDIR)" -bb packaging/manbo.spec
	@echo
	@find $(TOPDIR)/RPMS -name '*.rpm'

clean:
	rm -rf build
