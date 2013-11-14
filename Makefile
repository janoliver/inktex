all:
	mkdir -p "~/.config/inkscape/extensions"; \
	cp -r inktex/ inktex.inx ~/.config/inkscape/extensions
	@echo "Done."