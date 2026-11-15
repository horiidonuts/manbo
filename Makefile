NAME    := manbo
VERSION := $(shell sed -n 's/^Version:[[:space:]]*//p' packaging/manbo.spec)
TOPDIR  := $(CURDIR)/build/rpm
TARBALL := $(TOPDIR)/SOURCES/$(NAME)-$(VERSION).tar.gz

WIDGET  := plasma/io.github.horiidonuts.manbo

.PHONY: run tarball rpm clean widget-install widget-remove

run:
	python3 -m manbo

# install / update the Plasma widget for this user only (no RPM needed)
widget-install:
	kpackagetool6 -t Plasma/Applet -u $(WIDGET) 2>/dev/null || kpackagetool6 -t Plasma/Applet -i $(WIDGET)

widget-remove:
	kpackagetool6 -t Plasma/Applet -r io.github.horiidonuts.manbo

tarball:
	mkdir -p $(TOPDIR)/SOURCES
	tar --exclude='__pycache__' --exclude='*.pyc' \
	    --transform 's,^,$(NAME)-$(VERSION)/,' \
	    -czf $(TARBALL) bin data manbo plasma packaging Makefile README.md LICENSE

rpm: tarball
	rpmbuild --define "_topdir $(TOPDIR)" -bb packaging/manbo.spec
	@echo
	@find $(TOPDIR)/RPMS -name '*.rpm'

clean:
	rm -rf build
