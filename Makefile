NAME    := manbo
VERSION := $(shell sed -n 's/^Version:[[:space:]]*//p' packaging/manbo.spec)
TOPDIR  := $(CURDIR)/build/rpm
TARBALL := $(TOPDIR)/SOURCES/$(NAME)-$(VERSION).tar.gz

.PHONY: run tarball rpm clean

run:
	python3 -m manbo

tarball:
	mkdir -p $(TOPDIR)/SOURCES
	tar --exclude='__pycache__' --exclude='*.pyc' \
	    --transform 's,^,$(NAME)-$(VERSION)/,' \
	    -czf $(TARBALL) bin data manbo packaging Makefile README.md LICENSE

rpm: tarball
	rpmbuild --define "_topdir $(TOPDIR)" -bb packaging/manbo.spec
	@echo
	@find $(TOPDIR)/RPMS -name '*.rpm'

clean:
	rm -rf build
