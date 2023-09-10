PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DOCDIR = $(PREFIX)/share/doc/nrrdjrnl
BSHDIR = /etc/bash_completion.d

.PHONY: all install uninstall

all:

install:
	install -m755 -d $(BINDIR)
	install -m755 -d $(MANDIR)
	install -m755 -d $(DOCDIR)
	install -m755 -d $(BSHDIR)
	gzip -c doc/nrrdjrnl.1 > nrrdjrnl.1.gz
	install -m755 nrrdjrnl/nrrdjrnl.py $(BINDIR)/nrrdjrnl
	install -m644 nrrdjrnl.1.gz $(MANDIR)
	install -m644 README.md $(DOCDIR)
	install -m644 CHANGES $(DOCDIR)
	install -m644 LICENSE $(DOCDIR)
	install -m644 CONTRIBUTING.md $(DOCDIR)
	install -m644 auto-completion/bash/nrrdjrnl-completion.bash $(BSHDIR)
	rm -f nrrdjrnl.1.gz

uninstall:
	rm -f $(BINDIR)/nrrdjrnl
	rm -f $(MANDIR)/nrrdjrnl.1.gz
	rm -f $(BSHDIR)/nrrdjrnl-completion.bash
	rm -rf $(DOCDIR)

