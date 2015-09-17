all:
	mkdir -p "${HOME}/.config/inkscape/extensions"; \
	cp -r inktex/ inktex.inx "${HOME}/.config/inkscape/extensions"
	@echo "Done."
